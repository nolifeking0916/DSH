#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真人试测回收表（CSV）→ 流水线要的真实作答 JSON —— 票 #26 的前置工具。

这个脚本只做一件事：**把施测人填的回收登记表，变成流水线读得懂的几个文件**。

    回收登记表 CSV ──► real_samples.json     作业包 §六 格式，给 run_pilot.mjs / analyze.py
                   ──► excluded_ids.json     人工判定剔除的 id 清单，给 analyze.py --exclude
                   ──► 回收登记表_回收后.csv  登记表原样回带，供归档
                   ──► ingest_report.json    逐份样本的校验结论 + 提醒项

口径来源（逐条对应，不凭印象；括号里是出处）：

  · 作答文件格式（`meta` / `respondents[].id` / `.group` / `.responses` / `.times_ms`）
    ── 真人试测作业包_20261024.md §六
  · 登记表字段（组 / 岗位层级 / 部门 / 身份标识后 4 位 / 起止时刻 / 实际用时 /
    10 批累计用时 / 中途退出 / 复核申请 / 结果 JSON 文件名 / 作答质量备注）
    ── 真人试测作业包_20261024.md §四
  · 批次计时法（96 题分 10 批记累计用时，按每批题数折算每题均毫秒）
    ── 票 #26 §3（"工具已就位"里的第 3 条）
  · 批次切分的具体题数（第 1–9 批各 10 题 = 第 1–90 题，第 10 批 6 题 = 第 91–96 题）
    ── 票 #26 §3 的批次计时法；本工具把它写死成 BATCH_SIZES 并写进输出注释
  · 有效作答定义（96 题全作答、无中途退出、作答时长 ≥ 名义时长 40%）
    ── 真人试测作业包_20261024.md §二
  · 剔除样本不进信度统计、清单写进 analysis.json 留痕
    ── 真人试测作业包_20261024.md §六 + analyze.py 的 `--exclude`
  · `id` 不写完整身份证号（用测评编号或「后 4 位 + 编号」）
    ── 真人试测作业包_20261024.md §六
  · 组只有「内部候选人」「在职员工」两档
    ── 真人试测作业包_20261024.md §二 样本表 + §四 登记表

**这个脚本不产生信效度证据**，也不造任何真人数据：
它只是搬运施测人已经登记好的东西，并在转换前把不该带进统计的数据挡在门外。

用法：
    python3 pilot/ingest_real.py --template                        # 打印 CSV 模板（骨架 + 2 行假示例）
    python3 pilot/ingest_real.py --csv <in.csv> --out-dir <dir>     # 转换
    python3 pilot/ingest_real.py --selftest                         # 自检（只写 tempfile 临时目录）

产物（--out-dir 下）：
    real_samples.json / excluded_ids.json / 回收登记表_回收后.csv / ingest_report.json

退出码：0 = 成功；1 = 有硬错误（**不写任何输出文件**）；2 = 命令行用法错误。
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import io
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ITEMS_PATH = os.path.join(ROOT, "items", "m1_items.json")
OUT = os.path.join(HERE, "out")

# ------------------------------------------------------------------ 口径常量
N_ITEMS = 96                       # 作业包 §二 / §六：第一项 96 题
DIMS = ["INT", "SNT", "TFS", "JPS"]
DIM_PER = 24                       # 作业包 §二 样本表：四维各 24 题
GROUPS = ["内部候选人", "在职员工"]   # 作业包 §二 / §四
LEVELS = ["专员", "经理", "总监", "其他"]  # 作业包 §四 登记表
BATCH_COLS = ["b%d" % i for i in range(1, 11)]
# 票 #26 §3：96 题分 10 批记累计用时。本工具把切分写死：
# 第 1–9 批各 10 题（第 1–90 题），第 10 批 6 题（第 91–96 题）。
BATCH_SIZES = [10, 10, 10, 10, 10, 10, 10, 10, 10, 6]
BATCH_SPLIT_NOTE = ("批次切分：第 1–9 批各 10 题（第 1–90 题），第 10 批 6 题（第 91–96 题）；"
                    "每题均毫秒 = 该批累计用时 ÷ 该批题数（四舍五入到整数毫秒）")
NOMINAL_SESSION_MIN = 90.0         # 作业包 §二：限时 90 分钟（三项合计）
WINDOW_TOLERANCE_MIN = 2.0         # 起止时刻与 actual_min 的容差（分钟）
FAST_ITEM_MS = 3000                # analyze.py detect_anomalies 的「平均每题 < 3 秒」旗标
DEMO_ID_PREFIX = "DEMO-FAKE-"      # 模板示例行的 id 前缀：带着它进真跑 = 假数据混入
MISSING_TOKENS = {"", "-", "—", "－", "/", "NA", "na", "N/A", "n/a", "无", "null", "None"}

CSV_HEADER = [
    "id", "group", "level", "dept", "id4", "start_at", "end_at", "actual_min",
] + BATCH_COLS + [
    "answers", "midway_exit", "exit_at", "review_request", "result_json",
    "quality_note", "exclude_reason",
]

TIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
    "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
]
TIME_HINT = "支持的写法如 2026-10-25 09:00 / 2026-10-25 09:00:00 / 2026-10-25T09:00 / 2026-10-25"

# 完整身份证号（18 位新证 / 15 位老证）—— 作业包 §六 明令不许写进 id
ID_PII_PATTERNS = [
    (re.compile(r"^\d{17}[\dXx]$"), "18 位身份证号"),
    (re.compile(r"^\d{15}$"), "15 位身份证号"),
]

OUT_REAL = "real_samples.json"
OUT_EXCLUDED = "excluded_ids.json"
OUT_REGISTRY = "回收登记表_回收后.csv"
OUT_REPORT = "ingest_report.json"


# ------------------------------------------------------------------ 小工具
def now_iso() -> str:
    """生成时间（带本地时区偏移）。"""
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def is_missing(raw: str | None) -> bool:
    """空值判定：空串、`-` 这类占位都算「未知」。"""
    return (raw or "").strip() in MISSING_TOKENS


def clean(raw: str | None) -> str:
    return (raw or "").strip()


def read_text(path: str) -> tuple[str | None, str | None]:
    """读 CSV 文本。优先 utf-8-sig（Excel 导出的 BOM），退回 gb18030（Windows 另存为）。"""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc), None
        except UnicodeDecodeError:
            continue
    return None, "文件编码既不是 UTF-8 也不是 GB18030，请另存为 UTF-8 CSV"


def parse_time(raw: str | None) -> tuple[dt.datetime | None, str | None]:
    """解析起止时刻。返回 (datetime | None, 错误说明 | None)。未知 → (None, None)。"""
    s = clean(raw)
    if s in MISSING_TOKENS:
        return None, None
    for fmt in TIME_FORMATS:
        try:
            return dt.datetime.strptime(s, fmt), None
        except ValueError:
            continue
    try:
        return dt.datetime.fromisoformat(s), None
    except ValueError:
        pass
    return None, "无法解析（%s）" % TIME_HINT


def parse_answers(raw: str | None) -> tuple[list[int] | None, str | None]:
    """解析 answers 字段。

    作业包 §六：`responses` 是 96 个 0/1（0 = 选 a 侧，1 = 选 b 侧），
    顺序与 `items/m1_items.json` 的题目顺序一一对应。

    接受两种写法：
      · 紧凑：96 个字符连写，如 "0101..."；
      · 分隔：96 个 0/1 用逗号或空格分隔（中文逗号、顿号、分号同样认）。
    返回 (列表 | None, 错误说明 | None)。
    """
    s = clean(raw)
    if not s:
        return None, "为空（这一列不能空：作业包 §六 要求 96 题全部作答）"
    seps = " \t,，、;；"
    if any(ch in s for ch in seps):
        tokens = [t for t in re.split(r"[\s,，、;；]+", s) if t]
        if len(tokens) != N_ITEMS:
            return None, "分隔后是 %d 个值，应为 %d 个" % (len(tokens), N_ITEMS)
        bad = [t for t in tokens if t not in ("0", "1")]
        if bad:
            return None, "含非 0/1 的值：%s" % "、".join(sorted(set(bad))[:5])
        return [int(t) for t in tokens], None
    if len(s) != N_ITEMS:
        return None, "长度 %d，应为 %d" % (len(s), N_ITEMS)
    bad = sorted(set(ch for ch in s if ch not in "01"))
    if bad:
        return None, "含非法字符：%s（只允许 0 和 1）" % "、".join(bad[:5])
    return [int(ch) for ch in s], None


def fold_batch_times(batches: list[int]) -> list[int]:
    """把 10 批累计用时折算成 96 个每题均毫秒（票 #26 §3）。

    第 1–9 批各 10 题 → 每批 ÷ 10；第 10 批 6 题 → ÷ 6。
    四舍五入到整数毫秒（用整数算，避免浮点误差）。
    """
    times: list[int] = []
    for total_ms, n in zip(batches, BATCH_SIZES):
        per = (total_ms + n // 2) // n
        times.extend([per] * n)
    return times


def batch_split_doc() -> dict:
    """批次切分说明（写进 real_samples.json 的 meta 与 ingest_report.json）。"""
    ranges = []
    start = 1
    for idx, n in enumerate(BATCH_SIZES, start=1):
        ranges.append({"batch": idx, "first_item": start, "last_item": start + n - 1, "count": n})
        start += n
    return {
        "batches": len(BATCH_SIZES),
        "sizes": list(BATCH_SIZES),
        "ranges": ranges,
        "rule": BATCH_SPLIT_NOTE,
        "source": "票 #26 §3 批次计时法（96 题分 10 批记累计用时，按每批题数折算每题均毫秒）",
    }


def load_items() -> tuple[list[dict], str | None]:
    """读题库并核对题数与四维分布。题目顺序就是 responses 的顺序（作业包 §六）。"""
    try:
        with open(ITEMS_PATH, encoding="utf-8") as f:
            m1 = json.load(f)
    except Exception as exc:  # noqa: BLE001
        return [], "读不到题库 %s：%s" % (ITEMS_PATH, exc)
    items = m1.get("items") or []
    if len(items) != N_ITEMS:
        return items, "题库 %s 有 %d 题，应为 %d 题" % (ITEMS_PATH, len(items), N_ITEMS)
    for d in DIMS:
        n = sum(1 for it in items if it.get("dim") == d)
        if n != DIM_PER:
            return items, "题库 %s 的 %s 维有 %d 题，应为 %d 题" % (ITEMS_PATH, d, n, DIM_PER)
    return items, None


# ------------------------------------------------------------------ 校验
def _err(line: int, row_no: int, field: str, code: str, message: str) -> dict:
    """一条硬错误。line = CSV 物理行号（第 1 行是表头），row_no = 数据行序号（从 1 起）。"""
    return {
        "line": line, "row": row_no, "field": field, "code": code, "message": message,
        "where": "CSV 第 %d 行（数据第 %d 行）字段 %s" % (line, row_no, field),
    }


def _warn(line: int, row_no: int, field: str, code: str, message: str, source: str) -> dict:
    """一条提醒项（不阻断，先进 ingest_report.json）。"""
    return {
        "line": line, "row": row_no, "field": field, "code": code, "message": message,
        "source": source,
    }


def check_row(row: dict, line: int, row_no: int,
             seen_ids: dict[str, int]) -> tuple[dict, list[dict], list[dict]]:
    """校验一行。返回 (结论记录, 硬错误列表, 提醒项列表)。"""
    errors: list[dict] = []
    warns: list[dict] = []

    # ---- id：非空、不重复、不是完整身份证号、不是模板示例行（作业包 §六）
    rid = clean(row.get("id"))
    if not rid:
        errors.append(_err(line, row_no, "id", "id_empty", "为空。id 用测评编号或「后 4 位 + 编号」（作业包 §六）"))
    else:
        if rid.startswith(DEMO_ID_PREFIX):
            errors.append(_err(line, row_no, "id", "id_demo_row",
                               "是模板示例行的假数据 id（%s 前缀），请整行删掉后再跑" % DEMO_ID_PREFIX))
        for pat, label in ID_PII_PATTERNS:
            if pat.match(rid):
                errors.append(_err(line, row_no, "id", "id_pii",
                                   "疑似%s。作业包 §六 明令 id 不得写完整身份证号" % label))
                break
        if rid in seen_ids:
            errors.append(_err(line, row_no, "id", "id_duplicate",
                               "与第 %d 行的 id 重复（回收核对与防重复提交用）" % seen_ids[rid]))
        else:
            seen_ids[rid] = line

    # ---- group：只能是两档（作业包 §二 / §四）
    grp = clean(row.get("group"))
    if not grp:
        errors.append(_err(line, row_no, "group", "group_empty",
                           "为空。组只能填：%s" % " / ".join(GROUPS)))
    elif grp not in GROUPS:
        errors.append(_err(line, row_no, "group", "group_invalid",
                           "「%s」不是有效组，只能填：%s" % (grp, " / ".join(GROUPS))))

    # ---- 岗位层级：缺了只提醒（作业包 §四 是登记项，不是硬约束）
    level = clean(row.get("level"))
    if is_missing(level):
        warns.append(_warn(line, row_no, "level", "missing_level",
                            "缺岗位层级（作业包 §四：专员 / 经理 / 总监 / 其他）", "作业包 §四"))
    elif level not in LEVELS:
        warns.append(_warn(line, row_no, "level", "level_unknown",
                            "岗位层级「%s」不在 %s 内（作业包 §四）" % (level, " / ".join(LEVELS)),
                            "作业包 §四"))

    # ---- 部门：在职员工必填（作业包 §四：部门 = 在职员工填）
    dept = clean(row.get("dept"))
    if is_missing(dept) and grp == "在职员工":
        warns.append(_warn(line, row_no, "dept", "missing_dept",
                            "在职员工缺部门（作业包 §四：部门由在职员工填）", "作业包 §四"))

    # ---- 身份标识后 4 位（作业包 §四：不记全号）
    id4 = clean(row.get("id4"))
    if is_missing(id4):
        warns.append(_warn(line, row_no, "id4", "missing_id4",
                            "缺身份标识后 4 位（作业包 §四）", "作业包 §四"))
    else:
        for pat, label in ID_PII_PATTERNS:
            if pat.match(id4):
                errors.append(_err(line, row_no, "id4", "id4_pii",
                                   "疑似%s。作业包 §四：身份标识只记后 4 位，不记全号" % label))
                break
        else:
            if len(id4) > 4:
                warns.append(_warn(line, row_no, "id4", "id4_too_long",
                                    "身份标识超过 4 位（%d 位），确认不是完整证件号（作业包 §四）" % len(id4),
                                    "作业包 §四"))

    # ---- 起止时刻：可解析且 end ≥ start；缺失不算错（作业包 §四）
    t_start, e_start = parse_time(row.get("start_at"))
    t_end, e_end = parse_time(row.get("end_at"))
    if e_start:
        errors.append(_err(line, row_no, "start_at", "time_unparsable",
                           "%s。未知可以填 -（作业包 §四）" % e_start))
    if e_end:
        errors.append(_err(line, row_no, "end_at", "time_unparsable",
                           "%s。未知可以填 -（作业包 §四）" % e_end))
    if t_start and t_end and t_end < t_start:
        errors.append(_err(line, row_no, "end_at", "time_reversed",
                           "收卷时刻早于开始时刻（%s < %s）" % (clean(row.get("end_at")),
                                                             clean(row.get("start_at")))))
    if not t_start:
        warns.append(_warn(line, row_no, "start_at", "missing_start",
                            "缺开始时刻，无法核对时长（作业包 §二 的时长异常判定要用）", "作业包 §二 / §四"))
    if not t_end:
        warns.append(_warn(line, row_no, "end_at", "missing_end",
                            "缺收卷时刻，无法核对时长（作业包 §二 的时长异常判定要用）", "作业包 §二 / §四"))

    # ---- 实际用时（分钟）：只提醒
    actual_raw = clean(row.get("actual_min"))
    actual_min = None
    if is_missing(actual_raw):
        warns.append(_warn(line, row_no, "actual_min", "missing_actual_min",
                            "缺实际用时（作业包 §二：时长 ≥ 名义时长 40% 才算有效作答）", "作业包 §二 / §四"))
    else:
        try:
            actual_min = float(actual_raw)
        except ValueError:
            warns.append(_warn(line, row_no, "actual_min", "actual_min_unparsable",
                                "实际用时「%s」不是数字" % actual_raw, "作业包 §四"))
    window_min = None
    if t_start and t_end:
        window_min = (t_end - t_start).total_seconds() / 60.0
        if actual_min is not None and abs(actual_min - window_min) > WINDOW_TOLERANCE_MIN:
            warns.append(_warn(line, row_no, "actual_min", "actual_min_mismatch",
                                "实际用时 %g 分钟与起止时刻推算的 %g 分钟相差 %g 分钟"
                                % (actual_min, window_min, abs(actual_min - window_min)),
                                "作业包 §二 / §四"))
        if window_min > NOMINAL_SESSION_MIN:
            warns.append(_warn(line, row_no, "end_at", "session_over_nominal",
                                "起止时刻跨度 %g 分钟，超过 §二 的限时 90 分钟（三项合计），需在质量备注里写明原因"
                                % window_min, "作业包 §二"))

    # ---- b1..b10：10 个都在、都是正整数
    batches: list[int] = []
    for col in BATCH_COLS:
        raw = clean(row.get(col))
        if not raw:
            errors.append(_err(line, row_no, col, "batch_missing",
                               "为空。96 题分 10 批记累计用时，这一批必须填（票 #26 §3）"))
            batches.append(0)
            continue
        if not re.match(r"^\d+$", raw):
            errors.append(_err(line, row_no, col, "batch_invalid",
                               "「%s」不是非负整数（毫秒）" % raw))
            batches.append(0)
            continue
        val = int(raw)
        if val <= 0:
            errors.append(_err(line, row_no, col, "batch_invalid",
                               "必须为正整数毫秒，实际是 %d" % val))
            batches.append(0)
            continue
        batches.append(val)

    # ---- answers：96 个 0/1，必填
    responses, a_err = parse_answers(row.get("answers"))
    if a_err:
        code = "answers_empty" if "为空" in a_err else "answers_invalid"
        errors.append(_err(line, row_no, "answers", code,
                           "%s（作业包 §六：96 个 0/1，0 = 选 a 侧，1 = 选 b 侧）" % a_err))

    # ---- 中途退出 / 复核申请：登记项，有内容就提醒（作业包 §三 / §二）
    midway = clean(row.get("midway_exit"))
    if not is_missing(midway) and midway != "无":
        warns.append(_warn(line, row_no, "midway_exit", "midway_exit",
                            "登记了中途退出「%s」：作业包 §二 的有效作答要求「无中途退出」，"
                            "这份要人工复核是否剔除" % midway, "作业包 §二 / §三"))
    review = clean(row.get("review_request"))
    if not is_missing(review) and review != "无":
        warns.append(_warn(line, row_no, "review_request", "review_request",
                            "登记了复核申请「%s」：作业包 §三，5 个工作日内受理并记录结论" % review,
                            "作业包 §三"))

    # ---- 结果 JSON 文件名 / 作答质量备注（作业包 §三 收卷时 / §四）
    result_json = clean(row.get("result_json"))
    if is_missing(result_json):
        warns.append(_warn(line, row_no, "result_json", "missing_result_json",
                            "缺结果 JSON 文件名（作业包 §三：当场收回，作业包 §四：归档用）",
                            "作业包 §三 / §四"))
    note = clean(row.get("quality_note"))
    if is_missing(note):
        warns.append(_warn(line, row_no, "quality_note", "missing_quality_note",
                            "缺作答质量备注（作业包 §四：施测人现场观察，例如是否中途接电话、是否明显敷衍）",
                            "作业包 §四"))

    # ---- 人工判定剔除（exclude_reason 非空；`-` / `无` / 空 = 不剔除）
    exclude_reason = clean(row.get("exclude_reason"))
    excluded = not is_missing(exclude_reason) and exclude_reason != "无"
    if exclude_reason == "无":
        warns.append(_warn(line, row_no, "exclude_reason", "exclude_reason_is_wu",
                            "exclude_reason 填了「无」→ 按**不剔除**处理；要剔除就把剔除理由写具体",
                            "作业包 §四 / §六 剔除清单"))

    # ---- 时长一致性（提醒）
    total_ms = sum(batches) if all(b > 0 for b in batches) else 0
    per_item_mean = total_ms / float(N_ITEMS) if total_ms else 0.0
    if total_ms:
        if per_item_mean < FAST_ITEM_MS:
            warns.append(_warn(line, row_no, "b1..b10", "fast_items",
                                "批次累计用时折算下来平均每题 %d 毫秒（< 3 秒），"
                                "analyze.py 的异常盲检会打「平均每题 < 3 秒」的旗标" % round(per_item_mean),
                                "票 #26 §3 / analyze.py detect_anomalies"))
        if actual_min is not None and total_ms > actual_min * 60000 + 60000:
            warns.append(_warn(line, row_no, "b1..b10", "batch_total_gt_actual_min",
                                "批次累计用时合计 %g 分钟，比登记的实际用时 %g 分钟还长，"
                                "两者对不上（作业包 §四 的两列应自洽）"
                                % (total_ms / 60000.0, actual_min), "作业包 §四"))
        if window_min is not None and total_ms > window_min * 60000:
            warns.append(_warn(line, row_no, "b1..b10", "batch_total_gt_window",
                                "批次累计用时合计 %g 分钟，比起止时刻跨度 %g 分钟还长，"
                                "b1..b10 应填「本批用时」而不是从开考起的累计"
                                % (total_ms / 60000.0, window_min), "票 #26 §3"))

    record = {
        "line": line, "row": row_no, "id": rid, "group": grp, "level": level, "dept": dept,
        "id4": id4, "start_at": clean(row.get("start_at")), "end_at": clean(row.get("end_at")),
        "actual_min": actual_raw, "batches": {c: v for c, v in zip(BATCH_COLS, batches)},
        "batch_total_ms": total_ms, "total_min": round(total_ms / 60000.0, 3),
        "per_item_ms_mean": round(per_item_mean, 1),
        "excluded": excluded, "exclude_reason": exclude_reason,
        "midway_exit": midway, "review_request": review, "result_json": result_json,
        "quality_note": note,
        "status": "error" if errors else ("warn" if warns else "ok"),
        "warnings": warns,
    }
    return record, errors, warns


# ------------------------------------------------------------------ 主转换
def ingest(csv_path: str, out_dir: str) -> tuple[dict | None, dict, list[dict]]:
    """读 CSV → 校验 → 组装。返回 (payload, report, hard_errors)。

    hard_errors 非空时 **不写任何输出文件**（调用方负责报错退出）。
    """
    hard_errors: list[dict] = []
    warns_all: list[dict] = []

    items, items_err = load_items()
    if items_err:
        hard_errors.append({"line": 0, "row": 0, "field": "items", "code": "items_invalid",
                            "message": items_err, "where": "题库 " + ITEMS_PATH})
    item_ids = [it.get("id") for it in items]

    text, enc_err = read_text(csv_path)
    if enc_err:
        hard_errors.append({"line": 0, "row": 0, "field": "file", "code": "encoding",
                            "message": enc_err, "where": "CSV 文件"})
        return None, {}, hard_errors

    # 读行：整行空 / 以 # 开头的注释行跳过（模板自带注释行）
    records: list[tuple[int, list[str]]] = []
    skipped = 0
    reader = csv.reader(io.StringIO(text, newline=""))
    for row in reader:
        line = reader.line_num
        if not row or (row[0].lstrip().startswith("#")):
            skipped += 1
            continue
        records.append((line, row))
    if not records:
        hard_errors.append({"line": 0, "row": 0, "field": "file", "code": "empty_file",
                            "message": "CSV 里没有任何数据行（表头都没读到）", "where": "CSV 文件"})
        return None, {}, hard_errors

    header = [h.strip() for h in records[0][1]]
    if header != CSV_HEADER:
        missing = [c for c in CSV_HEADER if c not in header]
        extra = [c for c in header if c not in CSV_HEADER]
        hard_errors.append({
            "line": records[0][0], "row": 0, "field": "header", "code": "header_mismatch",
            "message": "表头与固定表头不一致。缺列：%s；多出的列：%s；固定表头：%s"
                       % ("、".join(missing) or "无", "、".join(extra) or "无", ",".join(CSV_HEADER)),
            "where": "CSV 第 %d 行（表头）" % records[0][0],
        })
        return None, {}, hard_errors

    seen_ids: dict[str, int] = {}
    records_out: list[dict] = []
    responses_all: list[list[int]] = []
    times_all: list[list[int]] = []
    excluded_ids: list[str] = []

    for idx, (line, cells) in enumerate(records[1:], start=1):
        if all(not c.strip() for c in cells):
            skipped += 1
            continue
        if len(cells) > len(header):
            hard_errors.append(_err(line, idx, "(整行)", "too_many_fields",
                                    "字段数 %d 多于表头 %d 列" % (len(cells), len(header))))
            continue
        row = {c: (cells[i] if i < len(cells) else "") for i, c in enumerate(header)}
        record, errors, warns = check_row(row, line, idx, seen_ids)
        hard_errors.extend(errors)
        warns_all.extend(warns)
        records_out.append(record)
        if errors:
            continue    # 这一行有问题就不往下组装，留给报错输出
        responses_all.append(parse_answers(row.get("answers"))[0])
        times_all.append(fold_batch_times([int(clean(row.get(c))) for c in BATCH_COLS]))
        if record["excluded"]:
            excluded_ids.append(record["id"])

    # ---- 组装 real_samples.json（作业包 §六）
    respondents = []
    for rec, resp, times in zip(records_out, responses_all, times_all):
        if not resp or not times:
            continue
        respondents.append({
            "id": rec["id"],
            "group": rec["group"],
            "responses": resp,
            "times_ms": times,
        })

    meta = {
        "note": "真人试测作答样本（由 pilot/ingest_real.py 从回收登记表 CSV 转换生成；格式见作业包 §六）",
        "generated_at": now_iso(),
        "source_csv": os.path.abspath(csv_path),
        "csv_rows": len(records_out),
        "n_respondents": len(respondents),
        "items_source": os.path.relpath(ITEMS_PATH, ROOT),
        "batch_split": batch_split_doc(),
        "excluded_ids": excluded_ids,
        "warning_count": len(warns_all),
    }
    payload = {"meta": meta, "respondents": respondents}

    report = {
        "note": "真人试测回收表转换报告：逐份样本的校验结论与提醒项",
        "generated_at": meta["generated_at"],
        "source_csv": os.path.abspath(csv_path),
        "csv_rows": len(records_out),
        "skipped_rows": skipped,
        "n_respondents": len(respondents),
        "n_excluded": len(excluded_ids),
        "excluded_ids": excluded_ids,
        "items_source": os.path.relpath(ITEMS_PATH, ROOT),
        "items_count": len(items),
        "item_order": item_ids,
        "batch_split": batch_split_doc(),
        "hard_errors": hard_errors,
        "samples": records_out,
        "warnings": warns_all,
        "warning_count": len(warns_all),
        "next_commands": [
            "node pilot/run_pilot.mjs %s" % os.path.join(out_dir, OUT_REAL),
            "cp pilot/out/scored.json pilot/out/real_scored.json",
            "python3 pilot/analyze.py --real %s --scored pilot/out/real_scored.json --exclude %s"
            % (os.path.join(out_dir, OUT_REAL), os.path.join(out_dir, OUT_EXCLUDED)),
        ],
    }
    return payload, report, hard_errors


def write_outputs(out_dir: str, payload: dict, report: dict, csv_path: str) -> list[str]:
    """写四个产物。只有确认无硬错误后才会被调用。"""
    os.makedirs(out_dir, exist_ok=True)
    written = []

    p = os.path.join(out_dir, OUT_REAL)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    written.append(p)

    p = os.path.join(out_dir, OUT_EXCLUDED)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(report["excluded_ids"], f, ensure_ascii=False, indent=1)
    written.append(p)

    # 登记表原样回带：一个字节都不改，供归档对账（作业包 §四）
    p = os.path.join(out_dir, OUT_REGISTRY)
    shutil.copyfile(csv_path, p)
    written.append(p)

    p = os.path.join(out_dir, OUT_REPORT)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    written.append(p)
    return written


# ------------------------------------------------------------------ 模板
def template_text() -> str:
    """CSV 模板：注释头 + 固定表头 + 2 行**假数据**示例。

    示例行是假的（id 带 DEMO-FAKE- 前缀、备注里写明「示例行假数据」），
    且 ingest_real.py 会拒绝带该前缀的 id —— 防止示例行忘了删就进真跑。
    """
    demo_answers = "01" * 48
    header = ",".join(CSV_HEADER)
    row1 = ",".join([
        "DEMO-FAKE-0001", "内部候选人", "经理", "人力资源部", "0000",
        "2026-10-25 09:00", "2026-10-25 10:05", "65",
        "60000", "55000", "52000", "58000", "61000", "60000", "57000", "59000", "62000", "36000",
        demo_answers, "无", "-", "无", "DEMO-FAKE-0001_结果.json", "示例行（假数据，请整行删掉）", "-",
    ])
    row2 = ",".join([
        "DEMO-FAKE-0002", "在职员工", "专员", "运营部", "1234",
        "2026-10-25 14:00", "2026-10-25 15:10", "70",
        "62000", "58000", "60000", "55000", "59000", "61000", "57000", "60000", "58000", "33000",
        demo_answers, "有", "2026-10-25 14:55", "无", "DEMO-FAKE-0002_结果.json",
        "示例行（假数据，请整行删掉）", "中途接电话，明显敷衍",
    ])
    lines = [
        "# 回收登记表 CSV 模板 —— 下面两行是**假数据示例**，请整行删掉后再填（工具会拒绝 DEMO-FAKE- 前缀的 id）",
        "# 字段口径：真人试测作业包_20261024.md §四；转换工具：pilot/ingest_real.py（配套说明 ingest_real_说明.md）",
        "# answers：96 个 0/1，0 = 选 a 侧，1 = 选 b 侧，顺序与 items/m1_items.json 的题目顺序一一对应",
        "# b1..b10：每批**本批用时**（毫秒）。第 1–9 批各 10 题（第 1–90 题），第 10 批 6 题（第 91–96 题）",
        "#        b2 = 答第 2 批那 10 题花的时间，不是从开考到第 2 批的累计 —— 填错会导致时长判定全歪",
        "# group：只能填 内部候选人 / 在职员工；level：专员 / 经理 / 总监 / 其他",
        "# start_at / end_at：2026-10-25 09:00 这样写；未知填 -（不填不算错，但时长异常就判不了）",
        "# id：写测评编号或「后 4 位 + 编号」，**不要写完整身份证号**（作业包 §六）",
        "# exclude_reason：填了非空 = 人工判定剔除；该 id 会进 excluded_ids.json，样本本身仍留在 real_samples.json 里",
        header,
        row1,
        row2,
    ]
    return "\n".join(lines)


def print_template() -> None:
    print(template_text())


# ------------------------------------------------------------------ 自检
def _selftest_csv(path: str, rows: list[list[str]]) -> None:
    """写一份自检 CSV（文件名带 SELFTEST_ 前缀，内容一眼看出是自检用）。"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("# SELFTEST_ 自检用 CSV：内容是假数据，不要当真人样本用\n")
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        for r in rows:
            w.writerow(r)


def _selftest_ok_row(rid: str, group: str = "内部候选人", answers: str | None = None,
                     exclude_reason: str = "-") -> list[str]:
    ans = answers if answers is not None else "01" * 48
    return [
        rid, group, "经理", "人力资源部", "0000",
        "2026-10-25 09:00", "2026-10-25 10:00", "60",
        "60000", "55000", "52000", "58000", "61000", "60000", "57000", "59000", "62000", "36000",
        ans, "无", "-", "无", rid + "_结果.json", "SELFTEST_ 自检用假数据", exclude_reason,
    ]


def run_selftest() -> int:
    """自检：在 tempfile 临时目录里造 fixture，断言转换与报错都对。

    硬约束：**所有临时文件都在 tempfile 目录内**，绝不写进 pilot/out/。
    """
    checks: list[tuple[bool, str]] = []

    def check(ok: bool, label: str) -> None:
        checks.append((bool(ok), label))

    out_before = sorted(os.listdir(OUT)) if os.path.isdir(OUT) else None

    tmpdir = tempfile.mkdtemp(prefix="SELFTEST_ingest_real_")
    try:
        # ---------- 1. 正例：能跑通，产物结构对 ----------
        good = os.path.join(tmpdir, "SELFTEST_valid.csv")
        _selftest_csv(good, [
            _selftest_ok_row("SELFTEST-OK-1"),
            _selftest_ok_row("SELFTEST-OK-2", group="在职员工", exclude_reason="中途接电话，明显敷衍"),
        ])
        outdir = os.path.join(tmpdir, "SELFTEST_out")
        payload, report, errors = ingest(good, outdir)
        check(not errors, "正例：无硬错误（实际 %d 条）" % len(errors))
        check(payload is not None and len(payload["respondents"]) == 2, "正例：2 份样本")
        if payload:
            r0 = payload["respondents"][0]
            check(len(r0["responses"]) == 96, "正例：responses 长度 96")
            check(len(r0["times_ms"]) == 96, "正例：times_ms 长度 96")
            check(r0["group"] == "内部候选人", "正例：group 透传")
            check(set(r0["responses"]) <= {0, 1}, "正例：responses 只有 0/1")
            # 批次折算：b1=60000/10 → 6000ms；b10=36000/6 → 6000ms
            check(r0["times_ms"][0] == 6000, "正例：第 1 批每题 6000 毫秒（60000÷10）")
            check(r0["times_ms"][95] == 6000, "正例：第 10 批每题 6000 毫秒（36000÷6）")
            check(all(r0["times_ms"][i] == r0["times_ms"][i // 10 * 10] for i in range(90)),
                  "正例：第 1–9 批每批 10 题同值")
            check(payload["meta"]["batch_split"]["sizes"] == BATCH_SIZES, "正例：meta 写明批次切分")
            check(payload["meta"]["csv_rows"] == 2, "正例：meta 记 CSV 行数")
        check(report.get("excluded_ids") == ["SELFTEST-OK-2"], "正例：exclude_reason 非空的 id 进剔除清单")
        check(len(payload["respondents"]) == 2, "正例：被剔除的样本仍留在 real_samples.json 里")

        # 写盘 + 下游契约检查（作业包 §六 / analyze.py / run_pilot.mjs 的读法）
        written = write_outputs(outdir, payload, report, good)
        check(all(os.path.exists(p) for p in written), "正例：4 个产物都写出来了")
        with open(os.path.join(outdir, OUT_EXCLUDED), encoding="utf-8") as f:
            check(json.load(f) == ["SELFTEST-OK-2"], "正例：excluded_ids.json 是 JSON 数组")
        with open(os.path.join(outdir, OUT_REAL), encoding="utf-8") as f:
            real = json.load(f)
        check(set(real.keys()) == {"meta", "respondents"}, "正例：real_samples.json 顶层只有 meta / respondents")
        check(all(set(r.keys()) == {"id", "group", "responses", "times_ms"}
                  for r in real["respondents"]), "正例：每份样本只有 id / group / responses / times_ms")
        check(os.path.getsize(os.path.join(outdir, OUT_REGISTRY)) == os.path.getsize(good),
              "正例：回收登记表_回收后.csv 与原表一样大（原样回带）")

        # ---------- 2. 反例：四种错误都要被抓到，且不写任何输出文件 ----------
        bad = os.path.join(tmpdir, "SELFTEST_bad.csv")
        bad_rows = [
            _selftest_ok_row("SELFTEST-BAD-1"),                 # 正例行
            _selftest_ok_row("SELFTEST-BAD-2", answers="01" * 47),          # 长度错（94）
            _selftest_ok_row("SELFTEST-BAD-3", answers="01" * 47 + "2"),     # 非法字符
            _selftest_ok_row("SELFTEST-BAD-1"),                 # 重复 id
        ]
        _selftest_csv(bad, bad_rows)
        badout = os.path.join(tmpdir, "SELFTEST_out_bad")
        payload2, report2, errors2 = ingest(bad, badout)
        codes = {(e["row"], e["field"], e["code"]) for e in errors2}
        check((2, "answers", "answers_invalid") in codes, "反例：抓到 answers 长度错（第 2 行）")
        check((3, "answers", "answers_invalid") in codes, "反例：抓到 answers 非法字符（第 3 行）")
        check((4, "id", "id_duplicate") in codes, "反例：抓到重复 id（第 4 行）")
        # 报错文案要指到行与字段
        check(any(e["field"] == "answers" and "数据第 2 行" in e["where"]
                  for e in errors2), "反例：报错文案指到具体行与字段")
        # 走一遍 CLI：退出码非零，且一个输出文件都不许有
        buf_out, buf_err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            rc = main(["--csv", bad, "--out-dir", badout])
        check(rc == 1, "反例：CLI 有硬错误时退出码 = 1（实际 %d）" % rc)
        check(not os.path.exists(badout), "反例：有硬错误时不写任何输出文件（目录都没建）")
        check("没有写出任何输出文件" in buf_err.getvalue(), "反例：报错文案说清没写文件")

        # ---------- 3. 其他硬错误各来一条 ----------
        misc = os.path.join(tmpdir, "SELFTEST_misc.csv")
        row = _selftest_ok_row("SELFTEST-MISC-1")
        row[CSV_HEADER.index("group")] = "外部人员"          # 组不在枚举内
        row2 = list(_selftest_ok_row("SELFTEST-MISC-2"))
        row2[CSV_HEADER.index("b3")] = "0"                    # 批次不是正整数
        row3 = list(_selftest_ok_row("SELFTEST-MISC-3"))
        row3[CSV_HEADER.index("end_at")] = "2026-10-25 08:00"  # 收卷早于开始
        row4 = list(_selftest_ok_row("SELFTEST-MISC-4"))
        row4[CSV_HEADER.index("id")] = "110101199001011234"    # 完整身份证号
        row5 = list(_selftest_ok_row("SELFTEST-MISC-5"))
        row5[CSV_HEADER.index("id")] = "DEMO-FAKE-9999"       # 模板示例行没删
        _selftest_csv(misc, [row, row2, row3, row4, row5])
        _, _, errors3 = ingest(misc, os.path.join(tmpdir, "SELFTEST_out_misc"))
        codes3 = {(e["row"], e["code"]) for e in errors3}
        check((1, "group_invalid") in codes3, "反例：组不在枚举内被拦下")
        check((2, "batch_invalid") in codes3, "反例：批次用时不是正整数被拦下")
        check((3, "time_reversed") in codes3, "反例：收卷早于开始被拦下")
        check((4, "id_pii") in codes3, "反例：id 写完整身份证号被拦下")
        check((5, "id_demo_row") in codes3, "反例：模板示例行没删被拦下")

        # ---------- 4. 提醒项不阻断 ----------
        soft = os.path.join(tmpdir, "SELFTEST_soft.csv")
        row = _selftest_ok_row("SELFTEST-SOFT-1", group="在职员工")
        row[CSV_HEADER.index("level")] = "-"
        row[CSV_HEADER.index("dept")] = "-"
        row[CSV_HEADER.index("actual_min")] = "20"
        _selftest_csv(soft, [row])
        payload4, report4, errors4 = ingest(soft, os.path.join(tmpdir, "SELFTEST_out_soft"))
        check(not errors4, "提醒项：缺 level / dept、actual_min 与起止矛盾都不阻断")
        wcodes = {w["code"] for w in report4["warnings"]}
        check("missing_level" in wcodes, "提醒项：记下缺岗位层级")
        check("missing_dept" in wcodes, "提醒项：记下缺部门")
        check("actual_min_mismatch" in wcodes, "提醒项：记下 actual_min 与起止时刻矛盾")
        check(payload4 is not None and len(payload4["respondents"]) == 1, "提醒项：样本照样生成")

        # ---------- 5. answers 的分隔写法 ----------
        sep = os.path.join(tmpdir, "SELFTEST_sep.csv")
        row = _selftest_ok_row("SELFTEST-SEP-1")
        row[CSV_HEADER.index("answers")] = ",".join(["0", "1"] * 48)
        _selftest_csv(sep, [row])
        payload5, _, errors5 = ingest(sep, os.path.join(tmpdir, "SELFTEST_out_sep"))
        check(not errors5, "分隔写法：逗号分隔的 96 个 0/1 被接受")
        check(payload5 is not None and payload5["respondents"][0]["responses"][:4] == [0, 1, 0, 1],
              "分隔写法：解析结果正确")

        # ---------- 6. 模板与固定表头一致 ----------
        tpl_lines = [ln for ln in template_text().splitlines() if ln and not ln.startswith("#")]
        check(tpl_lines[0] == ",".join(CSV_HEADER), "模板：表头与固定表头一致")
        check(len(tpl_lines) == 3, "模板：表头 + 2 行示例")
        check(all(ln.startswith("DEMO-FAKE-") for ln in tpl_lines[1:]), "模板：示例行明确是假数据")

        # ---------- 7. 自检没有碰 pilot/out/ ----------
        out_after = sorted(os.listdir(OUT)) if os.path.isdir(OUT) else None
        check(out_before == out_after, "自检没有写进 pilot/out/（文件清单不变）")
        check(all(p.startswith(tmpdir) for p in written), "自检产物全部落在 tempfile 目录内")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ------------------------------------------------------------ 打印结论
    failed = [label for ok, label in checks if not ok]
    print("== ingest_real.py 自检 ==")
    for ok, label in checks:
        print("  [%s] %s" % ("通过" if ok else "失败", label))
    print("自检项 %d，通过 %d，失败 %d" % (len(checks), len(checks) - len(failed), len(failed)))
    if failed:
        print("自检失败：")
        for label in failed:
            print("  - " + label)
        return 1
    print("自检通过：转换、报错、提醒项、批次折算、下游契约都符合预期。")
    return 0


# ------------------------------------------------------------------ CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="真人试测回收表 CSV → 流水线要的真实作答 JSON（票 #26 前置工具）",
        epilog=("示例：\n"
                "  python3 pilot/ingest_real.py --template\n"
                "  python3 pilot/ingest_real.py --csv 回收登记表.csv --out-dir pilot/out\n"
                "  python3 pilot/ingest_real.py --selftest\n"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--csv", metavar="PATH", help="施测人填好的回收登记表 CSV")
    ap.add_argument("--out-dir", metavar="DIR", help="产物输出目录")
    ap.add_argument("--template", action="store_true", help="打印 CSV 模板（表头 + 2 行假示例）")
    ap.add_argument("--selftest", action="store_true", help="自检（只在 tempfile 临时目录里跑）")
    args = ap.parse_args(argv)

    if args.template:
        print_template()
        return 0
    if args.selftest:
        return run_selftest()
    if not args.csv or not args.out_dir:
        ap.error("要转换请同时给 --csv 与 --out-dir（或者用 --template / --selftest）")
    if not os.path.exists(args.csv):
        print("找不到 CSV：%s" % args.csv, file=sys.stderr)
        return 1

    payload, report, errors = ingest(args.csv, args.out_dir)
    if errors:
        print("校验未通过：发现 %d 处硬错误，**没有写出任何输出文件**。" % len(errors), file=sys.stderr)
        for e in errors:
            print("  - %s：%s" % (e["where"], e["message"]), file=sys.stderr)
        print("请改 CSV 后重跑；「CSV 第 N 行」是物理行号，「数据第 M 行」是第几份样本"
              "（空行与 # 注释行不计入）。", file=sys.stderr)
        return 1

    written = write_outputs(args.out_dir, payload, report, args.csv)
    print("== 回收登记表转换完成 ==")
    print("  CSV：%s（%d 行样本）" % (os.path.abspath(args.csv), report["csv_rows"]))
    print("  样本 %d 份 · 剔除清单 %d 份 · 提醒项 %d 条"
          % (report["n_respondents"], report["n_excluded"], report["warning_count"]))
    for p in written:
        print("  写出 %s" % p)
    if report["excluded_ids"]:
        print("  剔除 id（人工判定，带 exclude_reason）：%s" % "、".join(report["excluded_ids"]))
    if report["warnings"]:
        print("  提醒项（不阻断，详见 ingest_report.json）：")
        for w in report["warnings"]:
            print("    - 第 %d 行 %s：%s" % (w["line"], w["field"], w["message"]))
    print("下一步：")
    for cmd in report["next_commands"]:
        print("  " + cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
