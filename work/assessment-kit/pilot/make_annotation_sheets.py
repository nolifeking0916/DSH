#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""票 #26 · 第 5/6 条：双人标注与锚定审计的盲版工作表（生成 / 校验 / 回收合并）。

为什么有这一层
--------------
`pilot/真人试测作业包_20261024.md` §五 给了规程与空白记录表，但没有可直接发出去的盲版表；
而 `items/m1_items.json` 每题都带 `anchor`（声明的有效端）与 `rationale`（判据理由）——
直接把题库发出去等于把答案一起发了。本脚本从题库生成：

  · 双人标注表（96 题，剥掉 anchor / rationale / theory）
  · 锚定审计表（24 题，题面左右换位；换位映射只进分析方密钥）
  · 给标注员看的一页说明（四维判据从题库 meta 里取，不手抄）

并把「两张填好的表 → analyze_annotations.py 能吃的 CSV」这条回收链也做掉（--merge-*）。

口径（照抄，不临时改）
--------------------
  · 票 #26 第 5 条：两名标注员独立标注 96 题、互不可见；某维分歧率 > 15% ⇒ 整维重标。
  · 票 #26 第 6 条：每维抽 6 题换位审计，命中率 ≥ 80%，否则该维题目重写。
  · 作业包 §五：24 题优先抽样清单（按字面锚合度从低到高）。
  · items/m1_design.md §三：每题一端是「更有效的一端」（anchor），选它记 1 分。

产物（pilot/标注/）
------------------
  01_标注员A_96题.xlsx / .csv        双人标注（A 用）
  02_标注员B_96题.xlsx / .csv        双人标注（B 用）
  03_锚定审计A_24题_换位版.xlsx/.csv  锚定审计（A 用，第一轮收齐后再发）
  04_锚定审计B_24题_换位版.xlsx/.csv
  锚定审计密钥_只给分析方.json         qid → 原有效端 / 换位后有效端；不给标注员
  README_标注员作业包_20261025.md      发给人看的一页说明（含四维判据）

命令
----
  python3 pilot/make_annotation_sheets.py --check          # 生成 + 逐项校验（默认）
  python3 pilot/make_annotation_sheets.py --check-only     # 只校验既有产物
  python3 pilot/make_annotation_sheets.py --merge-annotations A.xlsx B.xlsx --out pilot/out/annotations.csv
  python3 pilot/make_annotation_sheets.py --merge-audit 03.xlsx 04.xlsx --out pilot/out/audit.csv

合并后的两份 CSV 直接喂给：
  python3 pilot/analyze_annotations.py --annotations pilot/out/annotations.csv ``
      --audit pilot/out/audit.csv --out-dir pilot/out
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ITEMS_PATH = os.path.join(ROOT, "items", "m1_items.json")
PKG_PATH = os.path.join(HERE, "真人试测作业包_20261024.md")
OUT_DIR = os.path.join(HERE, "标注")
KEY_NAME = "锚定审计密钥_只给分析方.json"
README_NAME = "README_标注员作业包_20261025.md"
DATA_SHEET = "填写"
INSTR_SHEET = "说明"

ANN_HEAD = ["序号", "标注员", "题号", "维度", "选项a", "选项b",
            "你的选择（a 或 b）", "你的理由（可选，一句话）"]
AUD_HEAD = ["序号", "标注员", "题号", "维度", "选项a（换位后）", "选项b（换位后）",
            "你的选择（a 或 b）"]
ANN_FILES = {"A": "01_标注员A_96题", "B": "02_标注员B_96题"}
AUD_FILES = {"A": "03_锚定审计A_24题_换位版", "B": "04_锚定审计B_24题_换位版"}

# 审计题数：每维 6 题（票 #26 第 6 条 / 作业包 §五 / m1_design §六.4）
AUDIT_PER_DIM = 6
ITEMS_PER_DIM = 24

SIDE_RE = re.compile(r"^(?:选项|选择|答案|选|端|侧)?([abAB])(?:端|侧|项)?$")
FORBIDDEN_HEAD = ("anchor", "有效端", "rationale", "判据", "答案")


# ------------------------------------------------------------------ 读源
def load_bank():
    with open(ITEMS_PATH, encoding="utf-8") as f:
        raw = f.read()
    m1 = json.loads(raw)
    items = m1["items"]
    dims = m1.get("meta", {}).get("dimensions", [])
    dim_by_key = {d["key"]: d for d in dims}
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return items, dims, dim_by_key, sha


def load_audit_ids(items):
    """从作业包 §五 的优先抽样清单表里读 24 个题号（单一来源，不另抄一份）。"""
    if not os.path.exists(PKG_PATH):
        raise SystemExit("找不到作业包：%s" % PKG_PATH)
    pat = re.compile(r"^\|\s*[A-Z]{3}\s*\|\s*([A-Z]{3}-\d{2})\s*\|")
    ids = []
    with open(PKG_PATH, encoding="utf-8") as f:
        for line in f:
            m = pat.match(line.strip())
            if m:
                ids.append(m.group(1))
    known = {it["id"] for it in items}
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise SystemExit("作业包清单里出现了题库里没有的题号：%s" % "、".join(unknown))
    if len(ids) != len(set(ids)):
        raise SystemExit("作业包清单有重复题号")
    want = AUDIT_PER_DIM * len({it["dim"] for it in items})
    if len(ids) != want:
        raise SystemExit("作业包清单应为 %d 题（每维 %d），实际读到 %d 题" % (want, AUDIT_PER_DIM, len(ids)))
    return ids


# ------------------------------------------------------------------ 写表
def write_xlsx(path, head, rows, instr_rows, choice_idx):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = DATA_SHEET
    ws.append(head)
    bold = Font(bold=True)
    fill = PatternFill("solid", fgColor="EEF3EE")
    for c in ws[1]:
        c.font = bold
        c.fill = fill
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for r in rows:
        ws.append(r)
    ws.freeze_panes = "A2"
    widths = {"A": 6, "B": 8, "C": 11, "D": 14, "E": 34, "F": 34, "G": 16, "H": 30}
    for col, w in widths.items():
        if col <= chr(ord("A") + len(head) - 1):
            ws.column_dimensions[col].width = w
    for r in ws.iter_rows(min_row=2, max_row=len(rows) + 1, max_col=len(head)):
        for c in r:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    if choice_idx:
        col = chr(ord("A") + choice_idx)
        dv = DataValidation(type="list", formula1='"a,b"', allow_blank=True,
                            showErrorMessage=True, error="请填 a 或 b（不要填汉字）",
                            errorTitle="只能填 a 或 b")
        ws.add_data_validation(dv)
        dv.add("%s2:%s%d" % (col, col, len(rows) + 1))

    ws2 = wb.create_sheet(INSTR_SHEET)
    for r in instr_rows:
        ws2.append(r)
    for c in ws2[1]:
        c.font = bold
    ws2.column_dimensions["A"].width = 18
    ws2.column_dimensions["B"].width = 52
    ws2.column_dimensions["C"].width = 52
    for r in ws2.iter_rows(min_row=1, max_row=len(instr_rows)):
        for c in r:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    wb.save(path)


def write_csv(path, head, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)


# ------------------------------------------------------------------ 生成
def build():
    items, dims, dim_by_key, sha = load_bank()
    audit_ids = load_audit_ids(items)
    by_id = {it["id"]: it for it in items}
    os.makedirs(OUT_DIR, exist_ok=True)

    # 1) 标注表：题面按题库原顺序（a 在前），剥掉 anchor / rationale / theory
    for code in ("A", "B"):
        rows = []
        for n, it in enumerate(items, start=1):
            d = dim_by_key.get(it["dim"], {})
            rows.append([n, code, it["id"], "%s %s" % (it["dim"], d.get("name", "")),
                         it["a"], it["b"], "", ""])
        base = os.path.join(OUT_DIR, ANN_FILES[code])
        write_xlsx(base + ".xlsx", ANN_HEAD, rows, instr_rows_ann(dims, code), choice_idx=6)
        write_csv(base + ".csv", ANN_HEAD, rows)

    # 2) 审计表：同 24 题，题面左右换位；映射只进密钥
    key = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "source_items": "items/m1_items.json",
           "source_sha256": sha,
           "rule": "每题把原有效端换到另一侧显示（a/b 互换）；命中 = 换位后仍选中同一个行为（choice == swapped_anchor）",
           "items": []}
    for qid in audit_ids:
        it = by_id[qid]
        orig = it["anchor"]
        swapped = "b" if orig == "a" else "a"
        key["items"].append({"qid": qid, "dim": it["dim"], "orig_anchor": orig,
                             "swapped_anchor": swapped})
    for code in ("A", "B"):
        rows = []
        for n, entry in enumerate(key["items"], start=1):
            it = by_id[entry["qid"]]
            d = dim_by_key.get(it["dim"], {})
            # 换位 = 显示顺序互换；「选项a」显示原 b，「选项b」显示原 a
            rows.append([n, code, it["id"], "%s %s" % (it["dim"], d.get("name", "")),
                         it["b"], it["a"], ""])
        base = os.path.join(OUT_DIR, AUD_FILES[code])
        write_xlsx(base + ".xlsx", AUD_HEAD, rows, instr_rows_aud(dims, code), choice_idx=6)
        write_csv(base + ".csv", AUD_HEAD, rows)

    with open(os.path.join(OUT_DIR, KEY_NAME), "w", encoding="utf-8") as f:
        json.dump(key, f, ensure_ascii=False, indent=2)

    write_readme(dims, sha)


# ------------------------------------------------------------------ 说明文本
def _crit(d):
    return "定义：%s / 判据：%s" % (d.get("definition", ""), d.get("behavior", ""))


def instr_rows_ann(dims, code):
    rows = [["说明", "这一页给标注员 %s 自己看；填「填写」这张表。" % code, ""]]
    rows.append(["这份表做什么", "判断每题两端中，哪一端在管理岗位上更有效。这是题目质量检查，不是测验，不评价你。", ""])
    rows.append(["怎么填", "每题只能在 a / b 里选一个（下拉框）；理由可写可不写；序号 / 标注员 / 题号 / 维度 / 选项五列不要改。", ""])
    rows.append(["不要做什么", "不要查资料、不要问同事、不要看另一位标注员的表——两个人必须独立。", ""])
    rows.append(["要多久", "96 题，每题 20–30 秒，约 40–60 分钟；可以分两次做，做完一起交回。", ""])
    rows.append(["交回", "把填好的这一张表（xlsx 或 csv）原样发回；不要另存为新格式，不要合并单元格。", ""])
    for d in dims:
        rows.append(["维度 %s %s" % (d["key"], d.get("name", "")), _crit(d), ""])
    return rows


def instr_rows_aud(dims, code):
    rows = [["说明", "第二轮（锚定审计）：题面左右已经换过位置；仍然判断哪一端更有效。给标注员 %s。" % code, ""]]
    rows.append(["为什么有第二轮", "把有效端换到另一侧，看你还能不能认出同一个行为——认得出 = 题面把行为说清楚了。", ""])
    rows.append(["怎么填", "每题只能在 a / b 里选一个（下拉框）；序号 / 标注员 / 题号 / 维度 / 选项不要改。", ""])
    rows.append(["不要做什么", "不要翻第一轮那张表，也不要和别人对答案。", ""])
    rows.append(["要多久", "24 题，约 10–15 分钟。先做完第一轮，再等分析方通知做这一轮。", ""])
    for d in dims:
        rows.append(["维度 %s %s" % (d["key"], d.get("name", "")), _crit(d), ""])
    return rows


def write_readme(dims, sha):
    L = []
    L.append("# 标注员作业包（票 #26 · 第 5/6 条）")
    L.append("")
    L.append("> 生成：`python3 pilot/make_annotation_sheets.py`（题库 sha256 前 12 位 `%s`）；"
             "题库变了要重跑，否则表与题库对不上。" % sha[:12])
    L.append("")
    L.append("## 你要做的")
    L.append("")
    L.append("第一轮：填 `01_标注员A_96题.xlsx` 或 `02_标注员B_96题.xlsx`（谁做哪一张由分析方定），"
             "对 96 道题逐题判断「哪一端在管理岗位上更有效」。")
    L.append("第二轮：等分析方通知，再填 `03/04_锚定审计_24题_换位版`（题面左右换过位置，仍然判断哪一端更有效）。")
    L.append("")
    L.append("两张表都不含答案：题库里的「声明的有效端」与「判据理由」已经剥掉；"
             "换位映射只存在分析方那份密钥里。")
    L.append("")
    L.append("## 怎么填")
    L.append("")
    L.append("- 每题只选 a 或 b（表里是下拉框）；拿不准也必须选一个，理由里写「两端都说得通 / 判据落不下来」——"
             "这种题正是我们要挑出来的。")
    L.append("- 序号 / 标注员 / 题号 / 维度 / 选项五列不要改、不要排序、不要加行删行。")
    L.append("- 不要查资料、不要问人、不要看另一位标注员的表：两个人必须独立。")
    L.append("- 时间：第一轮 96 题约 40–60 分钟；第二轮 24 题约 10–15 分钟。")
    L.append("")
    L.append("## 四维判据（判断依据）")
    L.append("")
    L.append("| 维度 | 定义 | 判据（哪一端更有效） |")
    L.append("|---|---|---|")
    for d in dims:
        L.append("| %s %s | %s | %s |" % (d["key"], d.get("name", ""),
                                           d.get("definition", ""), d.get("behavior", "")))
    L.append("")
    L.append("## 收回来之后（分析方）")
    L.append("")
    L.append("```bash")
    L.append("# 两张填好的标注表 → analyze_annotations.py 能吃的 CSV")
    L.append("python3 pilot/make_annotation_sheets.py --merge-annotations \\")
    L.append("  pilot/标注/01_标注员A_96题.xlsx pilot/标注/02_标注员B_96题.xlsx \\")
    L.append("  --out pilot/out/annotations.csv")
    L.append("")
    L.append("# 两张填好的审计表 + 密钥 → 审计 CSV")
    L.append("python3 pilot/make_annotation_sheets.py --merge-audit \\")
    L.append("  pilot/标注/03_锚定审计A_24题_换位版.xlsx pilot/标注/04_锚定审计B_24题_换位版.xlsx \\")
    L.append("  --out pilot/out/audit.csv")
    L.append("")
    L.append("# 机器判定：每维分歧率 ≤ 15%、审计命中率 ≥ 80%")
    L.append("python3 pilot/analyze_annotations.py --annotations pilot/out/annotations.csv \\")
    L.append("  --audit pilot/out/audit.csv --out-dir pilot/out")
    L.append("```")
    L.append("")
    L.append("口径出处：`pilot/真人试测作业包_20261024.md` §五（双人标注 / 锚定审计 / 阈值）、"
             "`items/m1_design.md` §三（锚定判据）与 §六（标注与仲裁规程）、票 #26 第 5/6 条。")
    L.append("")
    with open(os.path.join(OUT_DIR, README_NAME), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


# ------------------------------------------------------------------ 校验
def _read_any(path):
    if path.lower().endswith(".xlsx"):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[DATA_SHEET] if DATA_SHEET in wb.sheetnames else wb.worksheets[0]
        rows = [[("" if v is None else str(v)) for v in r] for r in ws.iter_rows(values_only=True)]
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = [[c for c in r] for r in csv.reader(f)]
    head = [h.strip() for h in rows[0]]
    return head, [dict(zip(head, r)) for r in rows[1:]]


def _norm(s):
    return re.sub(r"\s+", "", str(s or ""))


def check():
    items, dims, dim_by_key, sha = load_bank()
    audit_ids = load_audit_ids(items)
    by_id = {it["id"]: it for it in items}
    fails = []

    key_path = os.path.join(OUT_DIR, KEY_NAME)
    with open(key_path, encoding="utf-8") as f:
        key = json.load(f)
    if key.get("source_sha256") != sha:
        fails.append("密钥里的题库 sha 与当前题库不一致（题库变了，重跑生成）")
    if len(key["items"]) != len(audit_ids):
        fails.append("密钥题数 %d != 优先清单 %d" % (len(key["items"]), len(audit_ids)))
    per_dim = {}
    for e in key["items"]:
        per_dim[e["dim"]] = per_dim.get(e["dim"], 0) + 1
        if e["orig_anchor"] == e["swapped_anchor"]:
            fails.append("%s 的换位没有变" % e["qid"])
        it = by_id.get(e["qid"])
        if not it:
            fails.append("%s 不在题库里" % e["qid"])
        elif it["anchor"] != e["orig_anchor"]:
            fails.append("%s 的原有效端与题库不一致" % e["qid"])
    for d in {it["dim"] for it in items}:
        if per_dim.get(d, 0) != AUDIT_PER_DIM:
            fails.append("维度 %s 审计题数 %d != %d" % (d, per_dim.get(d, 0), AUDIT_PER_DIM))

    # 泄漏检查：任何产物里都不能出现题库的 rationale / theory
    needles = []
    for it in items:
        for k in ("rationale", "theory"):
            t = _norm(it.get(k, ""))
            if len(t) >= 8:
                needles.append((it["id"], k, t))

    def scan(path, rows, label):
        for i, row in enumerate(rows, start=1):
            for k, v in row.items():
                nv = _norm(v)
                if not nv or nv in ("a", "b"):
                    continue
                for qid, field, t in needles:
                    if t in nv:
                        fails.append("%s 第 %d 行「%s」含 %s 的 %s（泄漏）" % (label, i, k, qid, field))
        for h in (rows[0].keys() if rows else []):
            low = h.lower()
            for bad in FORBIDDEN_HEAD:
                if bad in low:
                    fails.append("%s 表头「%s」含禁忌词「%s」" % (label, h, bad))

    for code in ("A", "B"):
        base = os.path.join(OUT_DIR, ANN_FILES[code])
        head, rows = _read_any(base + ".xlsx")
        if head != ANN_HEAD:
            fails.append("%s 表头与约定不一致" % base)
        scan(base + ".xlsx", rows, ANN_FILES[code])
        if len(rows) != len(items):
            fails.append("%s 行数 %d != %d" % (ANN_FILES[code], len(rows), len(items)))
        seen = set()
        for r in rows:
            qid = (r.get("题号") or "").strip()
            if qid in seen:
                fails.append("%s 题号重复：%s" % (ANN_FILES[code], qid))
            seen.add(qid)
            it = by_id.get(qid)
            if not it:
                fails.append("%s 出现题库里没有的题号：%s" % (ANN_FILES[code], qid))
                continue
            if (r.get("选项a") or "").strip() != it["a"] or (r.get("选项b") or "").strip() != it["b"]:
                fails.append("%s %s 的题面顺序不是题库原顺序" % (ANN_FILES[code], qid))
            if (r.get("你的选择（a 或 b）") or "").strip():
                fails.append("%s %s 的选择列不是空的（盲表不该预填）" % (ANN_FILES[code], qid))
            if (r.get("标注员") or "").strip() != code:
                fails.append("%s %s 的标注员列不是 %s" % (ANN_FILES[code], qid, code))
        if seen != {it["id"] for it in items}:
            fails.append("%s 题号集合与题库不一致" % ANN_FILES[code])

        base = os.path.join(OUT_DIR, AUD_FILES[code])
        head, rows = _read_any(base + ".xlsx")
        if head != AUD_HEAD:
            fails.append("%s 表头与约定不一致" % base)
        scan(base + ".xlsx", rows, AUD_FILES[code])
        if len(rows) != len(audit_ids):
            fails.append("%s 行数 %d != %d" % (AUD_FILES[code], len(rows), len(audit_ids)))
        seen = set()
        for r in rows:
            qid = (r.get("题号") or "").strip()
            if qid in seen:
                fails.append("%s 题号重复：%s" % (AUD_FILES[code], qid))
            seen.add(qid)
            it = by_id.get(qid)
            if not it:
                fails.append("%s 出现题库里没有的题号：%s" % (AUD_FILES[code], qid))
                continue
            if (r.get("选项a（换位后）") or "").strip() != it["b"] or \
               (r.get("选项b（换位后）") or "").strip() != it["a"]:
                fails.append("%s %s 的题面没有换位" % (AUD_FILES[code], qid))
            if (r.get("你的选择（a 或 b）") or "").strip():
                fails.append("%s %s 的选择列不是空的（盲表不该预填）" % (AUD_FILES[code], qid))
        if seen != set(audit_ids):
            fails.append("%s 题号集合与优先清单不一致" % AUD_FILES[code])

    if not os.path.exists(os.path.join(OUT_DIR, README_NAME)):
        fails.append("缺少 %s" % README_NAME)

    print("题库：%d 题 / %d 维；审计：%d 题（每维 %d）"
          % (len(items), len(dims), len(audit_ids), AUDIT_PER_DIM))
    print("输出目录：%s" % OUT_DIR)
    for code in ("A", "B"):
        print("  %-30s xlsx + csv" % ANN_FILES[code])
        print("  %-30s xlsx + csv" % AUD_FILES[code])
    print("  %-30s 仅分析方" % KEY_NAME)
    print("  %-30s 给标注员" % README_NAME)
    if fails:
        print("\n校验失败 %d 项：" % len(fails))
        for f in fails[:60]:
            print("  ✗ %s" % f)
        if len(fails) > 60:
            print("  …… 共 %d 项" % len(fails))
        return 1
    print("\n校验通过：96×2 标注表（原顺序、无答案键）+ 24×2 审计表（已换位）+ 密钥 + 说明。")
    return 0


# ------------------------------------------------------------------ 回收合并
def _side(v):
    s = (v or "").strip().lower().replace(" ", "")
    m = SIDE_RE.match(s)
    return m.group(1).lower() if m else None


def _read_filled(path):
    head, rows = _read_any(path)
    need = ["标注员", "题号", "你的选择（a 或 b）"]
    miss = [c for c in need if c not in head]
    if miss:
        raise SystemExit("%s 缺少列 %s（实际表头：%s）" % (path, "、".join(miss), "、".join(head)))
    out, bad = [], []
    for i, r in enumerate(rows, start=2):
        qid = (r.get("题号") or "").strip()
        if not qid:
            continue
        side = _side(r.get("你的选择（a 或 b）"))
        if side is None:
            bad.append("第 %d 行 %s 的选择是「%s」" % (i, qid, r.get("你的选择（a 或 b）")))
            continue
        out.append({"qid": qid,
                    "annotator": (r.get("标注员") or "").strip(),
                    "choice": side,
                    "comment": (r.get("你的理由（可选，一句话）") or "").strip()})
    if bad:
        raise SystemExit("%s 有 %d 处填得不对：\n  %s" % (path, len(bad), "\n  ".join(bad[:20])))
    if not out:
        raise SystemExit("%s 一行有效作答都没有" % path)
    codes = {(r["annotator"] or "").upper() for r in out}
    if len(codes) != 1:
        raise SystemExit("%s 的「标注员」列不唯一：%s" % (path, "、".join(sorted(codes))))
    return out


def merge_annotations(paths, out_path):
    items, dims, dim_by_key, sha = load_bank()
    known = {it["id"] for it in items}
    merged, codes = [], []
    for p in paths:
        rows = _read_filled(p)
        code = rows[0]["annotator"].upper()
        codes.append(code)
        seen = set()
        for r in rows:
            if r["qid"] not in known:
                raise SystemExit("%s 出现题库里没有的题号：%s" % (p, r["qid"]))
            if r["qid"] in seen:
                raise SystemExit("%s 题号重复：%s" % (p, r["qid"]))
            seen.add(r["qid"])
        miss = known - seen
        if miss:
            raise SystemExit("%s 还缺 %d 题没填（例如 %s）" % (p, len(miss), "、".join(sorted(miss)[:5])))
        merged.extend([dict(r, annotator=code) for r in rows])
    if len(set(codes)) != len(codes):
        raise SystemExit("两份表的「标注员」列重复了：%s" % "、".join(codes))
    merged.sort(key=lambda r: (r["annotator"], r["qid"]))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["qid", "annotator", "choice", "comment"])
        for r in merged:
            w.writerow([r["qid"], r["annotator"], r["choice"], r["comment"]])
    print("已合并 %d 行（标注员 %s）→ %s" % (len(merged), " / ".join(codes), out_path))
    return 0


def merge_audit(paths, out_path):
    items, dims, dim_by_key, sha = load_bank()
    key_path = os.path.join(OUT_DIR, KEY_NAME)
    with open(key_path, encoding="utf-8") as f:
        key = json.load(f)
    key_by_qid = {e["qid"]: e for e in key["items"]}
    rows_out, codes = [], []
    for p in paths:
        rows = _read_filled(p)
        code = rows[0]["annotator"].upper()
        codes.append(code)
        seen = set()
        for r in rows:
            e = key_by_qid.get(r["qid"])
            if not e:
                raise SystemExit("%s 出现不在审计清单里的题号：%s" % (p, r["qid"]))
            if r["qid"] in seen:
                raise SystemExit("%s 题号重复：%s" % (p, r["qid"]))
            seen.add(r["qid"])
            rows_out.append({"qid": r["qid"], "orig_anchor": e["orig_anchor"],
                             "swapped_anchor": e["swapped_anchor"],
                             "annotator": code, "choice": r["choice"]})
        miss = set(key_by_qid) - seen
        if miss:
            raise SystemExit("%s 还缺 %d 题没填（例如 %s）" % (p, len(miss), "、".join(sorted(miss)[:5])))
    if len(set(codes)) != len(codes):
        raise SystemExit("两份表的「标注员」列重复了：%s" % "、".join(codes))
    rows_out.sort(key=lambda r: (r["qid"], r["annotator"]))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["qid", "orig_anchor", "swapped_anchor", "annotator", "choice"])
        for r in rows_out:
            w.writerow([r["qid"], r["orig_anchor"], r["swapped_anchor"], r["annotator"], r["choice"]])
    print("已合并 %d 行（标注员 %s）→ %s" % (len(rows_out), " / ".join(codes), out_path))
    return 0


# ------------------------------------------------------------------ 入口
def main(argv=None):
    ap = argparse.ArgumentParser(description="票 #26 · 标注/审计盲版工作表")
    ap.add_argument("--check", action="store_true", help="生成后逐项校验（默认行为）")
    ap.add_argument("--check-only", action="store_true", help="只校验既有产物，不重新生成")
    ap.add_argument("--merge-annotations", nargs=2, metavar=("A", "B"),
                    help="合并两份填好的标注表 → analyze_annotations.py 的 --annotations")
    ap.add_argument("--merge-audit", nargs=2, metavar=("A", "B"),
                    help="合并两份填好的审计表 + 密钥 → analyze_annotations.py 的 --audit")
    ap.add_argument("--out", help="合并输出路径")
    a = ap.parse_args(argv)

    if a.merge_annotations:
        if not a.out:
            raise SystemExit("--merge-annotations 需要 --out")
        return merge_annotations(a.merge_annotations, a.out)
    if a.merge_audit:
        if not a.out:
            raise SystemExit("--merge-audit 需要 --out")
        return merge_audit(a.merge_audit, a.out)

    if not a.check_only:
        build()
    return check()


if __name__ == "__main__":
    sys.exit(main())
