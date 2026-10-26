#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""云端作答 → 试测流水线的数据桥（票 #26 · 云上版 #33）。

云端把每份作答存成一行（CloudBase PG 的 `public.responses`），试测流水线要的是
《真人试测作业包》§六 的形状：

    { meta: {...}, respondents: [ { id, group, responses: [96 个 0/1], times_ms: [...] } ] }

本脚本只做**搬运与体检**：不判定、不改题库、不写库、不改任何阈值。

    dump(JSON) ──▶ real_samples.json ──▶ node pilot/run_pilot.mjs ──▶ analyze.py --real
                   └──▶ excluded_ids.json   （剔除清单；默认不自动剔除）
                   └──▶ export_report.json  （体检报告：第 13 条的两个数 + 每份明细）

用法：

    # 1. 从云端导出一份 JSON（一行 SQL；PG 实例是 SHARED 租户，本机连不上，只能走这条）
    #    select code, respondent_name, id_last4, group_name, level, dept,
    #           started_at, submitted_at, duration_ms, m1_raw, unanswered_m1, limit_hint
    #    from public.responses order by id;
    # 2. 搬运 + 体检
    python3 pilot/export_from_db.py --dump pilot/out/responses_dump.json --out-dir pilot/out/
    # 3. 自检（造假数据，验搬运链路；**不构成信效度证据**）
    python3 pilot/export_from_db.py --selftest

口径出处：
  · 票 #26 第 13 条（完成整卷比例 / 省略作答比例）+ 裁定 D3（到点只提示、不自动交卷）
  · 《真人试测作业包》§六（real_samples.json 的形状）
  · cloudbase/migrations/20261025044500_create_responses_table.sql（云端表结构）
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ITEMS_PATH = os.path.join(ROOT, "items", "m1_items.json")

EXPECTED_ITEMS = 96        # 第一项题数（items/m1_items.json 的实数为准，下面会校验）
KNOWN_COLUMNS = {
    "code", "respondent_name", "id_last4", "group_name", "level", "dept",
    "started_at", "submitted_at", "duration_ms", "m1_raw", "m1_scores",
    "m2_result", "m3_result", "limit_hint", "unanswered_m1", "created_at",
    # 2026-10-26 补：第二、三项的**逐题作答**（云端 0e1f0fa 起才收这两列）。
    # 之前这两列不在白名单里 ⇒ 数据桥把它们丢了 ⇒ 第三项漏答在分析里根本看不见
    # （真实数据一进来就暴露：有一份第三项只答 18/40 仍交卷，旧口径却报「完成整卷 100%」）。
    "m2_answers", "m3_answers",
}

# 整卷题数：M1 96（题库 items/m1_items.json）+ M2（自评 + 情境）+ M3（推理）。
# 从仓内题库现读，不写死 —— 题库变了要自动跟上。
M2_BANK = os.path.join(ROOT, "data", "eq_bank_encoded.json")
M3_BANK = os.path.join(ROOT, "data", "logic_m3.json")


def expected_counts(item_count):
    """整卷期望题数：{m1, m2, m3, whole}。读不到题库时按已知值兜底并说明。"""
    m2 = m3 = None
    if os.path.exists(M2_BANK):
        with open(M2_BANK, encoding="utf-8") as f:
            eq = json.load(f)
        m2 = len(eq.get("self_items") or []) + len(eq.get("sjt") or [])
    if os.path.exists(M3_BANK):
        with open(M3_BANK, encoding="utf-8") as f:
            m3 = len(json.load(f).get("questions") or [])
    return {"m1": item_count, "m2": m2, "m3": m3,
            "whole": item_count + (m2 or 0) + (m3 or 0)}


# --------------------------------------------------------------- dump 读取
def read_dump(path):
    """读导出文件。接受三种形状：MCP 的 {data:{columns,rows}} / {rows} / 裸数组。"""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if isinstance(raw.get("data"), dict):
            raw = raw["data"]
        rows = raw.get("rows")
        if isinstance(rows, list):
            return rows
        if isinstance(raw.get("records"), list):
            return raw["records"]
    raise ValueError("认不出 dump 的形状：需要 rows 数组（MCP 输出 / {rows} / 裸数组皆可）")


# --------------------------------------------------------------- 单行体检
def parse_pg_array(value):
    """把 PostgreSQL 的数组字面量 "{0,1,NULL}" 解析成 Python 列表。

    从 SQL 导出时数组列回来的就是这种字面量（带引号的元素按 PG 规则转义）；
    驱动直接给列表时原样返回。
    """
    if value is None or isinstance(value, list):
        return value
    s = str(value).strip()
    if s.startswith("["):
        try:
            return json.loads(s)
        except Exception:
            return value
    if not (s.startswith("{") and s.endswith("}")):
        return value
    inner = s[1:-1]
    if not inner.strip():
        return []
    parts = []
    cur = ""
    inq = False
    for ch in inner:
        if ch == '"':
            inq = not inq
            continue
        if ch == "," and not inq:
            parts.append(cur.strip())
            cur = ""
            continue
        cur += ch
    parts.append(cur.strip())
    out = []
    for t in parts:
        if t.upper() == "NULL":
            out.append(None)
            continue
        try:
            out.append(int(t))
        except ValueError:
            out.append(t)
    return out


def parse_jsonb(value):
    """JSONB 列从 SQL 导出时是字符串，要还原成对象。"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def normalize_row(row):
    """把 SQL 导出的行规整成工具内部用的形状（数组 / JSONB 还原）。"""
    out = dict(row)
    if "m1_raw" in out:
        out["m1_raw"] = parse_pg_array(out["m1_raw"])
    for k in ("m1_scores", "m2_result", "m3_result", "limit_hint"):
        if k in out:
            out[k] = parse_jsonb(out[k])
    # 第二项：载荷里是**对象**（键 = 题序字符串）⇒ 摊成定长数组，空位 = None。
    if "m2_answers" in out:
        out["m2_answers"] = to_answer_list(out["m2_answers"])
    # 第三项：载荷里就是**数组**（长度 40，null = 未作答）。
    if "m3_answers" in out:
        out["m3_answers"] = parse_pg_array(out["m3_answers"])
    return out


def to_answer_list(value):
    """把第二项的逐题作答摊成数组：{ "0": 3, "2": 1 } → [3, None, 1]（空位 = 未答）。"""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return None
    if isinstance(value, dict):
        out = [None] * len(value)
        for k, v in value.items():
            try:
                i = int(k)
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(out):
                out[i] = v
        return out
    if isinstance(value, list):
        return value
    return None


def check_row(row, item_count, counts=None):
    """返回 (hard_errors, soft_warnings)。硬错误 = 整批阻断（与 ingest_real.py 同一纪律）。"""
    hard = []
    soft = []
    counts = counts or {}
    code = row.get("code")
    if not code:
        hard.append("缺 code（测评编号）：无法作样本 id")
    raw = row.get("m1_raw")
    if raw is None:
        hard.append("缺 m1_raw：没有逐题作答，算不出 α")
    elif not isinstance(raw, list):
        hard.append("m1_raw 不是数组")
    else:
        if len(raw) != item_count:
            hard.append("m1_raw 长度 %d ≠ %d" % (len(raw), item_count))
        # NULL = 未作答（合法）；非 0/1 的实数 = 脏数据（硬错误）
        bad = [i for i, v in enumerate(raw)
               if v is not None and not (isinstance(v, (int, float)) and not isinstance(v, bool) and v in (0, 1))]
        if bad:
            hard.append("m1_raw 里有非 0/1 的值（位置 %s）" % bad[:5])
        nulls = sum(1 for v in raw if v is None)
        declared = row.get("unanswered_m1")
        if nulls and declared is not None and declared != nulls:
            soft.append("unanswered_m1 记 %s，m1_raw 里实际有 %d 个空位，对不上" % (declared, nulls))
        if nulls and declared is None:
            soft.append("m1_raw 里有 %d 个空位但没有 unanswered_m1 列值" % nulls)
    if not row.get("respondent_name"):
        soft.append("缺姓名（HR 侧核对锚点；ADR-0004：不存完整身份证号）")
    if row.get("duration_ms") in (None, 0):
        soft.append("缺 duration_ms：异常检测的时长粗筛不可用")
    if row.get("unanswered_m1") not in (None, 0):
        soft.append("有 %s 题未答（省略作答；第 13 条要单列这个比例）" % row.get("unanswered_m1"))
    if not row.get("limit_hint"):
        soft.append("无 limit_hint 痕迹：到点提示后是否继续作答不可判")
    # 第二、三项的漏答（第 13 条要单列；第二、三项的成绩只在答完时成立）
    for key, label, total in (("m2_answers", "第二项", counts.get("m2")),
                              ("m3_answers", "第三项", counts.get("m3"))):
        seq = row.get(key)
        if seq is None:
            continue
        if not isinstance(seq, list):
            hard.append("%s 不是数组" % key)
            continue
        nulls = sum(1 for v in seq if v is None or v == "")
        if total and len(seq) != total:
            soft.append("%s 长度 %d ≠ 题库 %d（载荷被截断或题库版本不同）" % (label, len(seq), total))
        if nulls:
            soft.append("%s有 %d/%s 项未答（省略作答；该份的%s成绩不成立）"
                        % (label, nulls, total if total else "?", label))
    return hard, soft


# --------------------------------------------------------------- 搬运
def to_respondent(row, item_count):
    """数据库行 → 流水线要的 respondent。"""
    raw = [None if v is None else int(v) for v in row["m1_raw"]]
    nulls = sum(1 for v in raw if v is None)
    dur = row.get("duration_ms")
    if isinstance(dur, str):
        try:
            dur = int(dur)
        except Exception:
            dur = None
    times = [int(round(dur / item_count))] * item_count if isinstance(dur, (int, float)) and dur else None
    m2_seq = row.get("m2_answers")
    m3_seq = row.get("m3_answers")
    resp = {
        "id": row["code"],
        "group": row.get("group_name") or "未填",
        "responses": raw,
        # 第二、三项的逐题作答（2026-10-26 补：以前数据桥把这两列丢了，
        # 第三项漏答在分析里根本看不见）。None = 未作答。
        "m2_responses": m2_seq if isinstance(m2_seq, list) else None,
        "m3_responses": m3_seq if isinstance(m3_seq, list) else None,
        "name": row.get("respondent_name"),
        "idLast4": row.get("id_last4"),
        "level": row.get("level"),
        "dept": row.get("dept"),
        "started_at": row.get("started_at"),
        "submitted_at": row.get("submitted_at"),
        "duration_ms": dur,
        "unanswered_m1": row.get("unanswered_m1") if row.get("unanswered_m1") is not None else nulls,
        "limit_hint": row.get("limit_hint"),
        "m1_scores": row.get("m1_scores"),
        "m2_result": row.get("m2_result"),
        "m3_result": row.get("m3_result"),
    }
    if times is not None:
        resp["times_ms"] = times
        resp["times_inferred"] = True
        resp["times_note"] = ("逐题耗时未采（自助链接模式，服务端只在交卷那一刻看到请求）；"
                              "此处按总时长均摊。analyze.py 的两条时长粗筛只用总量，均摊与实测等价；"
                              "逐题级异常检测不可用。")
    return resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", metavar="PATH", help="从云端导出的响应表 JSON")
    ap.add_argument("--out-dir", default=os.path.join(HERE, "out"), help="产物目录")
    ap.add_argument("--keep-unanswered", action="store_true",
                    help="保留有未答题的份子进统计（默认剔除：维护者 2026-10-25 裁定 Q2=A）")
    ap.add_argument("--allow-partial", action="store_true",
                    help="允许带硬错误的行被跳过而不是整批阻断（默认：整批阻断、零输出）")
    ap.add_argument("--selftest", action="store_true", help="用造假数据自检搬运链路")
    args = ap.parse_args()

    item_count = EXPECTED_ITEMS
    try:
        with open(ITEMS_PATH, encoding="utf-8") as f:
            item_count = len(json.load(f)["items"])
    except Exception as exc:  # 题库读不到就按 96 走，但要说出来
        print("警告：读不到题库（%s），按 %d 题校验" % (exc, item_count))

    if args.selftest:
        return selftest(item_count)

    if not args.dump:
        print("用法：--dump PATH 或 --selftest")
        return 2

    counts = expected_counts(item_count)
    print("整卷题数：第一项 %d · 第二项 %s · 第三项 %s · 合计 %d"
          % (counts["m1"], counts["m2"], counts["m3"], counts["whole"]))

    rows = [normalize_row(r) for r in read_dump(args.dump)]
    hard_all = []
    soft_all = []
    seen = {}
    good = []
    for i, row in enumerate(rows):
        hard, soft = check_row(row, item_count, counts)
        code = row.get("code")
        if code:
            if code in seen:
                hard.append("code 重复（与第 %d 行相同）：%s" % (seen[code], code))
            else:
                seen[code] = i
        if hard:
            hard_all.append({"row": i, "code": code, "errors": hard})
        else:
            soft_all.append({"row": i, "code": code, "warnings": soft})
            good.append(row)

    if hard_all and not args.allow_partial:
        print("硬错误 %d 行 ⇒ 整批阻断，零输出文件（与 ingest_real.py 同一纪律）：" % len(hard_all))
        for h in hard_all:
            print("  第 %d 行（code=%s）：%s" % (h["row"], h["code"], "；".join(h["errors"])))
        return 1

    respondents = [to_respondent(r, item_count) for r in good]
    n = len(respondents)
    # ---- 第 13 条的两个数：口径分三层，别再混用 ----
    # 2026-10-26 修：原来「完成整卷」= 第一项 96 题满答 ⇒ 一份第三项只答 18/40 的作答
    # 也被算成「完成整卷 100%」。现在：
    #   first_item_complete  第一项 96 题满答（信效度分析只看这一项）
    #   whole_complete       整卷 212 位（96 + 76 + 40）全满
    #   omitted              任一项有空位
    for r in respondents:
        m1_seq = r.get("responses") or []
        m2_seq = r.get("m2_responses")
        m3_seq = r.get("m3_responses")
        r["m1_answered"] = sum(1 for x in m1_seq if x is not None)
        r["m2_answered"] = sum(1 for x in m2_seq if x is not None) if isinstance(m2_seq, list) else None
        r["m3_answered"] = sum(1 for x in m3_seq if x is not None) if isinstance(m3_seq, list) else None
        r["m1_unanswered"] = sum(1 for x in m1_seq if x is None)
        r["unanswered_count"] = r["m1_unanswered"]
        if r["m2_answered"] is not None:
            r["unanswered_count"] += (len(m2_seq) - r["m2_answered"])
        if r["m3_answered"] is not None:
            r["unanswered_count"] += (len(m3_seq) - r["m3_answered"])
        r["first_item_complete"] = (r["m1_answered"] == item_count)
        have_all_three = (r["m2_answered"] is not None) and (r["m3_answered"] is not None)
        r["whole_complete"] = (r["first_item_complete"] and have_all_three
                               and r["m2_answered"] == counts.get("m2")
                               and r["m3_answered"] == counts.get("m3"))
        r["whole_answered"] = r["m1_answered"] + (r["m2_answered"] or 0) + (r["m3_answered"] or 0)
    complete = sum(1 for r in respondents if r["whole_complete"])
    first_item_complete = sum(1 for r in respondents if r["first_item_complete"])
    incomplete = n - complete
    omitted = sum(1 for r in respondents if r["unanswered_count"] > 0)
    limit_hint_rows = [r["id"] for r in respondents if r.get("limit_hint")]

    # Q2=A（维护者 2026-10-25）：**第一项**有未答题的份子整份剔除，逐份登记。
    # 要保留就显式加 --keep-unanswered。
    # 分层口径（2026-10-26）：第二、三项漏答**不**剔除 —— 第一项满答的份子，
    # 第一项的信效度统计仍然干净；但第二/三项的成绩不成立，报告里必须写明。
    excluded = []
    if not args.keep_unanswered:
        excluded = [r["id"] for r in respondents if r["m1_unanswered"] > 0]

    samples = {
        "meta": {
            "source": "cloud-db",
            "dump": os.path.abspath(args.dump),
            "n_respondents": n,
            "item_count": item_count,
            "note": "云端导出的作答；含逐题作答 ⇒ 可算 α / 分半 / 极端题 / 社赞 / |r|",
        },
        "respondents": respondents,
    }

    os.makedirs(args.out_dir, exist_ok=True)
    out_samples = os.path.join(args.out_dir, "real_samples.json")
    out_excluded = os.path.join(args.out_dir, "excluded_ids.json")
    out_report = os.path.join(args.out_dir, "export_report.json")

    with open(out_samples, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=1)
    with open(out_excluded, "w", encoding="utf-8") as f:
        json.dump(excluded, f, ensure_ascii=False, indent=1)

    report = {
        "n_total": n,
        "counts": counts,
        "complete": complete,
        "first_item_complete": first_item_complete,
        "incomplete": incomplete,
        "omitted": omitted,
        "complete_ratio": round(complete / n, 4) if n else None,
        "first_item_complete_ratio": round(first_item_complete / n, 4) if n else None,
        "incomplete_ratio": round(incomplete / n, 4) if n else None,
        "omitted_ratio": round(omitted / n, 4) if n else None,
        "unanswered_total": sum(r["unanswered_count"] for r in respondents),
        "limit_hint_rows": limit_hint_rows,
        "excluded_ids": excluded,
        "exclude_unanswered_applied": not args.keep_unanswered,
        "hard_error_rows": hard_all,
        "soft_warning_rows": soft_all,
        "per_respondent": [
            {"id": r["id"], "group": r["group"], "duration_ms": r.get("duration_ms"),
             "m1_answered": r["m1_answered"], "m2_answered": r["m2_answered"],
             "m3_answered": r["m3_answered"], "whole_answered": r["whole_answered"],
             "unanswered": r["unanswered_count"],
             "first_item_complete": r["first_item_complete"],
             "whole_complete": r["whole_complete"],
             "limit_hint": bool(r.get("limit_hint"))}
            for r in respondents
        ],
        "note": ("第 13 条的两个数（2026-10-26 改口径）："
                 "**完成整卷比例 = 整卷 212 位（第一项 96 + 第二项 76 + 第三项 40）全答的份数占比**；"
                 "**省略作答比例 = 三项里任一项有未答题的份数占比**；"
                 "另报 first_item_complete（第一项 96 题满答的份数占比）—— 信效度分析只看第一项。"
                 "D3（到点只提示、不自动交卷）后不再有「被自动截断」的份数。"
                 "⚠ 分母只含**已交卷**的份子：中途退出的人不产生行，"
                 "所以这是「已交卷者里的完成率」，不是「有多少人做完了」。"
                 "Q2=A（维护者 2026-10-25 裁定）：有未答题的份子**整份剔除**、逐份登记（见 excluded_ids）；"
                 "要保留就显式加 --keep-unanswered。"),
    }
    with open(out_report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print("搬运 %d 份（跳过 %d 份硬错误行）" % (n, len(hard_all)))
    print("第13条：整卷答完 %d/%d（%s）  第一项满答 %d/%d（%s）  有省略作答 %d/%d（%s）  未答合计 %d  到点提示后仍作答 %d 份" % (
        complete, n, ("%.1f%%" % (report["complete_ratio"] * 100)) if n else "—",
        first_item_complete, n, ("%.1f%%" % (report["first_item_complete_ratio"] * 100)) if n else "—",
        omitted, n, ("%.1f%%" % (report["omitted_ratio"] * 100)) if n else "—",
        report["unanswered_total"], len(limit_hint_rows)))
    print("        （整卷 = 第一项 %d + 第二项 %s + 第三项 %s；分母只含已交卷的份子）"
          % (counts["m1"], counts["m2"], counts["m3"]))
    if soft_all:
        print("提醒 %d 行（不阻断，归档前扫一眼）" % len(soft_all))
    print("产物：%s / %s / %s" % (out_samples, out_excluded, out_report))
    return 0


def selftest(item_count):
    """造假数据验搬运链路。**这些数字不是信效度证据**（ADR-0007）。"""
    good = {
        "code": "DEMO-FAKE-0001", "respondent_name": "甲", "id_last4": "0000",
        "group_name": "内部候选人", "level": "专员", "dept": "市场部",
        "started_at": "2026-10-25T13:00:00+08:00", "submitted_at": "2026-10-25T13:40:00+08:00",
        "duration_ms": 2400000, "m1_raw": [0, 1] * (item_count // 2), "unanswered_m1": 0,
        "limit_hint": {"at": 5400000, "answered": 96},
    }
    partial = dict(good, code="DEMO-FAKE-0002",
                    m1_raw=[0, 1] * (item_count // 2 - 1) + [None, None],
                    unanswered_m1=2, limit_hint=None)
    broken = dict(good, code="DEMO-FAKE-0003", m1_raw=[0, 1, 5] + [0] * (item_count - 3))

    out_dir = os.path.join(HERE, "out", "selftest_tmp")
    os.makedirs(out_dir, exist_ok=True)
    dump_path = os.path.join(out_dir, "dump.json")
    with open(dump_path, "w", encoding="utf-8") as f:
        json.dump({"data": {"columns": sorted(good.keys()), "rows": [good, partial, broken]}}, f,
                  ensure_ascii=False, indent=1)

    print("自检 1：带硬错误的行 ⇒ 整批阻断、零输出")
    sys.argv = ["export_from_db.py", "--dump", dump_path, "--out-dir", out_dir]
    rc = hard_block_rc(dump_path, out_dir)
    print("  退出码 %s（期望非 0）→ %s" % (rc, "OK" if rc != 0 else "不通过"))
    ok = rc != 0

    print("自检 2：--allow-partial ⇒ 好的行照搬、坏的行被点名")
    rows = read_dump(dump_path)
    good_rows = [r for r in rows if r["code"] != "DEMO-FAKE-0003"]
    kept = [to_respondent(r, item_count) for r in good_rows]
    ok2 = len(kept) == 2 and kept[0]["responses"].__len__() == item_count
    print("  搬 %d 份（期望 2）→ %s" % (len(kept), "OK" if ok2 else "不通过"))
    ok = ok and ok2

    print("自检 3：第 13 条的两个数")
    complete = sum(1 for r in kept if r.get("unanswered_m1") in (None, 0))
    print("  完成整卷 %d/%d（期望 1/2）→ %s" % (complete, len(kept), "OK" if complete == 1 else "不通过"))
    ok = ok and complete == 1

    print("自检 4：times_ms 均摊与总量等价")
    t = kept[0]["times_ms"]
    ok4 = sum(t) == kept[0]["duration_ms"]
    print("  逐题合计 %d ms vs duration_ms %d → %s" % (
        sum(t), kept[0]["duration_ms"], "OK" if ok4 else "不通过"))
    ok = ok and ok4

    print("自检 5：缺 m1_raw 的行被硬错误拦下")
    h, _ = check_row({"code": "X"}, item_count)
    ok5 = any("缺 m1_raw" in x for x in h)
    print("  %s → %s" % (h, "OK" if ok5 else "不通过"))
    ok = ok and ok5

    print("自检结论：%s（**自检数据，不是真人数据，不构成信效度证据**）" % ("全部通过" if ok else "有项目未通过"))
    return 0 if ok else 1


def hard_block_rc(dump_path, out_dir):
    """跑一次带硬错误的搬运，返回退出码。"""
    argv = sys.argv
    try:
        sys.argv = ["export_from_db.py", "--dump", dump_path, "--out-dir", out_dir]
        return main()
    finally:
        sys.argv = argv


if __name__ == "__main__":
    sys.exit(main())
