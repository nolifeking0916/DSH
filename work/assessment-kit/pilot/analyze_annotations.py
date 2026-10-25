#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真人试测：双人标注 / 仲裁 / 锚定审计的机器判定 —— 票 #26 前置工具。

`analyze.py` 只做了**模拟版**锚定审计（`simulate_anchor_audit` / `anchor_audit_simulated`），
真人标注数据的入口一直是空的。本脚本补上这一段：吃**真实**的双人标注表、仲裁表、
锚定审计表，产出机器能判、人能读的结论。

口径来源（照抄执行，本脚本不临时改口径）：
  · `pilot/真人试测作业包_20261024.md` §五
      - 双人独立标注 → 逐题记录「是否一致」
      - 分歧率 = 分歧题数 ÷ 该维题数；> 15%（24 题中 ≥ 4 题）→ **该维整维重标**
      - 分歧题由测评负责人仲裁，仲裁理由写回题库 `rationale`（**裁决权在人，机器不代劳**）
      - 锚定审计每维抽 6 题，命中率 ≥ 80%，低于 → 该维题目重写
  · 同上 §七 判定阈值表：双人标注分歧率 ≤ 15%、锚定审计命中率 ≥ 80%
  · `items/m1_items.json`：96 题（INT/SNT/TFS/JPS 各 24 题），
    每题有 `id` / 题面 `a`,`b` / 声明的有效端 `anchor` / `rationale`

**裁决权在人，机器不代劳**：本脚本只读题库、只产出建议清单，
`rationale_suggestions` 是给人看的写回建议，**脚本本身一个字节都不写回题库**。

用法：
    python3 pilot/analyze_annotations.py --annotations annotations.csv \
        [--arbitration arbitration.csv] [--audit audit.csv] --out-dir pilot/out
    python3 pilot/analyze_annotations.py --selftest

产物：
    <out-dir>/annotations_report.json   机器判定结果
    <out-dir>/annotations_report.md     人读版（可直接贴进试测报告）
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ITEMS_PATH = os.path.join(ROOT, "items", "m1_items.json")
OUT = os.path.join(HERE, "out")

# ------------------------------------------------------------------ 判定阈值
DIMS_DEFAULT = ["INT", "SNT", "TFS", "JPS"]
DISAGREE_MAX = 0.15    # 作业包 §五.3 / §七：分歧率 > 15% → 该维整维重标
AUDIT_MIN = 0.80       # 作业包 §五 / §七：锚定审计命中率 ≥ 80%，低于 → 该维题目重写
AUDIT_SAMPLE_PER_DIM = 6   # 作业包 §五：每维抽 6 题

OVERALL_REWORK = "需返工"
OVERALL_PASS = "通过"
ACTION_PASS = "pass"
ACTION_RELABEL = "整维重标"
ACTION_REWRITE = "该维题目重写"
ACTION_NO_AUDIT = "未审计（无数据）"

ACTION_LABEL = {
    ACTION_PASS: "pass（无需返工）",
    ACTION_RELABEL: "整维重标",
    ACTION_REWRITE: "该维题目重写",
    ACTION_NO_AUDIT: "未审计（无数据）",
}

# 审计命中判定口径（hit_rule）
HIT_RULE_SIDE = "anchor_side"                    # 标注员记的是侧别字母
HIT_RULE_TEXT = "behavior_text"                  # 标注员记的是行为原文
HIT_RULE_FALLBACK = "fallback_swapped_anchor"    # 题面判不出 → 退回换位侧别口径

HIT_RULE_DESC = {
    HIT_RULE_SIDE: "记的是侧别字母：换位后仍选中原有效行为所在的一侧（choice == swapped_anchor）算命中",
    HIT_RULE_TEXT: "记的是行为原文：原文就是原有效端那一条行为算命中（与题面另一侧对不上）",
    HIT_RULE_FALLBACK: "题面判不出行为一致性：退回按「换位后选择与 swapped_anchor 相同」判定",
}

# CSV 表头。判定必需的列缺了就报错（宁可停下也不猜）；
# `comment` / `reason` 只是说明性文字，缺了不拦人，只提示。
ANN_COLS = ["qid", "annotator", "choice"]
ARB_COLS = ["qid", "final_choice"]
AUD_COLS = ["qid", "orig_anchor", "swapped_anchor", "annotator", "choice"]
ANN_OPT = ["comment"]
ARB_OPT = ["reason"]


# ------------------------------------------------------------------ 基础工具
def load_items(path=ITEMS_PATH):
    """读题库。返回 (items 列表, id → item 映射, 维度顺序)。"""
    if not os.path.exists(path):
        raise SystemExit("找不到题库文件：%s" % path)
    with open(path, encoding="utf-8") as f:
        m1 = json.load(f)
    items = m1["items"]
    by_id = {it["id"]: it for it in items}
    dims = [d["key"] for d in m1.get("meta", {}).get("dimensions", [])]
    if not dims:
        dims = [d for d in DIMS_DEFAULT if any(it["dim"] == d for it in items)]
    return items, by_id, dims


def read_csv_rows(path, required_cols, label, optional_cols=()):
    """读 CSV → 行列表。缺必需列直接报错（宁可停下也不猜）。"""
    if not path:
        return [], []
    if not os.path.exists(path):
        raise SystemExit("找不到 %s 文件：%s" % (label, path))
    warnings = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise SystemExit("%s 是空文件：%s" % (label, path))
        head = [h.strip() for h in reader.fieldnames]
        missing = [c for c in required_cols if c not in head]
        if missing:
            raise SystemExit("%s 缺少必需列 %s（实际表头：%s）" % (
                label, "、".join(missing), "、".join(head)))
        gone = [c for c in optional_cols if c not in head]
        if gone:
            warnings.append("%s 没有可选列 %s（不影响判定，只是少了说明文字）" % (
                label, "、".join(gone)))
        rows = []
        for raw in reader:
            row = {}
            for k, v in raw.items():
                if k is None:
                    continue
                row[k.strip()] = (v or "").strip()
            rows.append(row)
    return rows, warnings


SIDE_RE = re.compile(r"^(?:选项|选择|答案|选|端|侧)?([ab])(?:端|侧|项)?$")


def normalize_side(value):
    """把 'a' / 'A端' / '选a' 归一成 'a'；不是侧别就返回 None（不瞎猜）。"""
    if value is None:
        return None
    s = str(value).strip().lower().replace(" ", "")
    if not s:
        return None
    m = SIDE_RE.match(s)
    return m.group(1) if m else None


def norm_text(s):
    """归一化文本（去空白，含全角空格），用于题面行为文本比对。"""
    if s is None:
        return ""
    s = str(s).replace("　", " ").replace(" ", "").replace("\t", "")
    return s.strip()


def match_side_text(choice, text):
    """choice 文本与题面某一侧文本的匹配程度：'exact' / 'contains' / None。"""
    c = norm_text(choice)
    t = norm_text(text)
    if not c or not t:
        return None
    if c == t:
        return "exact"
    if c in t or t in c:
        return "contains"
    return None


def annotator_sort_key(code):
    """标注员代号排序：显式 A / B 优先，其余按代号排。

    报告里的 `annotator_a` / `annotator_b` 表示「第一 / 第二位标注员」，
    代号本身才是身份；用 A/B 代号时自然落在 A、B 两列。
    """
    up = (code or "").strip().upper()
    rank = 0 if up == "A" else (1 if up == "B" else 2)
    return (rank, up, code or "")


def pct(x):
    """比例转百分比文本；None 显示为破折号。"""
    return "—" if x is None else "%.1f%%" % (x * 100)


# ------------------------------------------------------- 锚定审计命中判定
def judge_audit_hit(item, orig_anchor, swapped_anchor, choice):
    """判定一条审计作答是否「命中」（换位后仍选中**同一个行为**）。

    返回 (hit, hit_rule, note)。

    口径（`orig_anchor` = 原有效端，`swapped_anchor` = 换位后有效端所在侧）：
      · 换位后，原有效端那一条行为出现在 `swapped_anchor` 侧；
      · 标注员记的是侧别字母 → 命中 = 选择 == swapped_anchor（hit_rule = anchor_side）；
      · 标注员记的是行为原文 → 命中原有效端那一条行为（hit_rule = behavior_text）；
      · 题面判不出行为一致性 → **不瞎猜**，退回按「换位后选择与 swapped_anchor 相同」
        判定（hit_rule = fallback_swapped_anchor），并在报告里写明用了哪种口径。
    """
    notes = []
    orig = normalize_side(orig_anchor)
    swapped = normalize_side(swapped_anchor)
    if orig is None:
        notes.append("原有效端缺失或不可识别")
    if swapped is None and orig is not None:
        swapped = "b" if orig == "a" else "a"
        notes.append("换位后有效端缺失，按换位规则取另一侧")
    elif swapped is None:
        notes.append("换位后有效端缺失且原有效端不可识别")

    letter = normalize_side(choice)
    hit = False
    rule = HIT_RULE_FALLBACK

    if letter is not None:
        if swapped is not None:
            rule = HIT_RULE_SIDE
            hit = (letter == swapped)
        else:
            notes.append("缺换位后有效端，无法按侧别判定，退回换位侧别口径")
    elif item is not None and orig is not None and swapped is not None:
        m_eff = match_side_text(choice, item.get(orig, ""))
        m_oth = match_side_text(choice, item.get(swapped, ""))
        if m_eff and not m_oth:
            rule = HIT_RULE_TEXT
            hit = True
            notes.append("标注员记的是行为原文，命中原有效端那一条行为")
        elif m_oth and not m_eff:
            rule = HIT_RULE_TEXT
            hit = False
            notes.append("标注员记的是行为原文，但选的是原有效端对面那一条行为")
        elif m_eff and m_oth:
            notes.append("题面两侧文本都能对上，无法判断行为一致性，退回换位侧别口径")
        else:
            notes.append("题面判不出行为一致性，退回换位侧别口径")
    else:
        notes.append("缺题面或缺侧别信息，退回换位侧别口径")

    return hit, rule, "；".join(notes)


def analyze_audit(audit_rows, by_id, warnings):
    """把「逐标注员」的审计行聚成「逐题命中」。

    作业包 §五的锚定审计记录表是一题一行（含标注员 A / B 两列与一列「命中」），
    而 CSV 是长表（每名标注员一行）。这里按题聚合：**两名标注员都命中**才算该题命中；
    一人命中一人没命中 → 该题记未命中，并单列出来让人复核。
    """
    per_q = {}
    rows_read = 0
    for idx, r in enumerate(audit_rows, start=1):
        rows_read += 1
        qid = r.get("qid", "")
        item = by_id.get(qid)
        if item is None:
            warnings.append("审计表第 %d 行题号不在题库：%s（该行不计入）" % (idx, qid))
            continue
        orig = r.get("orig_anchor", "")
        swapped = r.get("swapped_anchor", "")
        bank_anchor = item.get("anchor")
        if orig and normalize_side(orig) != bank_anchor:
            warnings.append(
                "审计表 %s 的原有效端（%s）与题库声明（%s）不一致，按审计表记录为准" % (
                    qid, orig, bank_anchor))
        hit, rule, note = judge_audit_hit(item, orig, swapped, r.get("choice", ""))
        per_q.setdefault(qid, {"dim": item["dim"], "rows": []})["rows"].append({
            "qid": qid,
            "dimension": item["dim"],
            "annotator": r.get("annotator", ""),
            "choice": r.get("choice", ""),
            "orig_anchor": orig,
            "swapped_anchor": swapped,
            "bank_anchor": bank_anchor,
            "hit": hit,
            "hit_rule": rule,
            "note": note,
        })

    questions = {}
    for qid, rec in per_q.items():
        hits = [x["hit"] for x in rec["rows"]]
        all_hit = bool(hits) and all(hits)
        rules = sorted({x["hit_rule"] for x in rec["rows"]})
        questions[qid] = {
            "qid": qid,
            "dimension": rec["dim"],
            "annotators": [x["annotator"] for x in rec["rows"]],
            "hit": all_hit,
            "mixed": any(hits) and not all_hit,
            "hit_rule": rules[0] if len(rules) == 1 else ("mixed(" + ",".join(rules) + ")"
                                                         if rules else None),
            "rows": rec["rows"],
        }
    return questions, rows_read


# ---------------------------------------------------------- 双人标注与分歧
def analyze_annotations(ann_rows, by_id, warnings):
    """按题聚合双人标注，列出分歧题与标注缺口。"""
    per_q = {}
    extra_qids = []
    for idx, r in enumerate(ann_rows, start=1):
        qid = r.get("qid", "")
        if qid not in by_id:
            extra_qids.append(qid)
            warnings.append("标注表第 %d 行题号不在题库：%s（该行不计入）" % (idx, qid))
            continue
        choice = normalize_side(r.get("choice", ""))
        if choice is None:
            warnings.append("标注表第 %d 行（题号 %s）的 choice 不是 a/b，该行不计入" % (idx, qid))
            continue
        annotator = r.get("annotator", "")
        if not annotator:
            warnings.append("标注表第 %d 行（题号 %s）没填标注员代号，该行不计入" % (idx, qid))
            continue
        per_q.setdefault(qid, {}).setdefault(annotator, []).append({
            "choice": choice, "comment": r.get("comment", ""), "row": idx,
        })

    disputes = []
    conflicts = []
    single = []      # 只来了一名标注员
    too_many = []    # 来了三名以上标注员
    for qid in sorted(per_q):
        item = by_id[qid]
        choices = {}
        bad = False
        for ann, lst in per_q[qid].items():
            uniq = sorted({x["choice"] for x in lst})
            if len(uniq) > 1:
                conflicts.append({"qid": qid, "dimension": item["dim"], "annotator": ann,
                                  "choices": uniq})
                bad = True
                continue
            choices[ann] = uniq[0]
        if bad:
            continue          # 该题有自相矛盾的标注，整题不计入分歧
        if len(choices) == 2:
            anns = sorted(choices.keys(), key=annotator_sort_key)
            a, b = anns[0], anns[1]
            if choices[a] != choices[b]:
                disputes.append({
                    "qid": qid,
                    "dimension": item["dim"],
                    "annotator_a": a,
                    "annotator_b": b,
                    "choice_a": choices[a],
                    "choice_b": choices[b],
                    "comment_a": _first_comment(per_q[qid], a),
                    "comment_b": _first_comment(per_q[qid], b),
                })
        elif len(choices) == 1:
            single.append(qid)
        elif len(choices) > 2:
            too_many.append(qid)

    for c in conflicts:
        warnings.append("题号 %s 的标注自相矛盾（同一标注员给了不同选择：%s），该题不计入分歧" % (
            c["qid"], "、".join(c["choices"])))
    for qid in too_many:
        warnings.append("题号 %s 出现三名以上标注员，该题不计入分歧（规程只允许两人）" % qid)

    return {"disputes": disputes, "single": single, "conflicts": conflicts,
            "too_many": too_many, "extra_qids": extra_qids}


def _first_comment(ann_map, annotator):
    """取该标注员在该题的第一条备注（仲裁时看原始理由用）。"""
    lst = ann_map.get(annotator) or []
    for x in lst:
        if x.get("comment"):
            return x["comment"]
    return ""


def analyze_arbitration(arb_rows, by_id, warnings):
    """读人工仲裁结果：qid → {final_choice, reason}。取值非法的不当成仲裁。"""
    arb = {}
    for idx, r in enumerate(arb_rows, start=1):
        qid = r.get("qid", "")
        if qid not in by_id:
            warnings.append("仲裁表第 %d 行题号不在题库：%s（该行不计入）" % (idx, qid))
            continue
        fc = normalize_side(r.get("final_choice", ""))
        if fc is None:
            warnings.append("仲裁表第 %d 行（题号 %s）的 final_choice 不是 a/b，按未仲裁处理" % (idx, qid))
            continue
        arb[qid] = {"final_choice": fc, "reason": r.get("reason", "")}
    return arb


# ------------------------------------------------------------------ 主判定
def build_report(ann_rows, arb_rows, aud_rows, items, by_id, dims,
                 source_files=None, data_kind="real", extra_warnings=None):
    """把三张表算成一份机器判定结果。"""
    warnings = list(extra_warnings or [])

    ann = analyze_annotations(ann_rows, by_id, warnings)
    arb = analyze_arbitration(arb_rows, by_id, warnings)
    audit_q, audit_rows_read = analyze_audit(aud_rows, by_id, warnings)

    disputes = ann["disputes"]
    for d in disputes:
        rec = arb.get(d["qid"])
        if rec:
            d["final_choice"] = rec["final_choice"]
            d["reason"] = rec["reason"]
            d["need_arbitration"] = False
        else:
            d["final_choice"] = None
            d["reason"] = None
            d["need_arbitration"] = True

    # 仲裁了一条没有分歧的题 → 多半是题号写错，提醒一下
    dispute_qids = {d["qid"] for d in disputes}
    for qid in sorted(arb):
        if qid not in dispute_qids:
            warnings.append("仲裁表里的题号 %s 在本批标注里没有分歧（可能题号写错，或该题两人本就一致）" % qid)

    # ---- 每维分歧率 ----
    per_dimension = {}
    for d in dims:
        dim_items = [it for it in items if it["dim"] == d]
        dim_disputes = [x for x in disputes if x["dimension"] == d]
        total = len(dim_items)
        dcount = len(dim_disputes)
        rate = (dcount / total) if total else None
        # 阈值判定：分歧率 > 0.15 → 该维整维重标（照抄 §五.3，不在这里改口径）
        passed = True if rate is None else bool(rate <= DISAGREE_MAX)
        annotated = [q for q in by_id if by_id[q]["dim"] == d and q in _annotated_qids(ann_rows)]
        per_dimension[d] = {
            "total": total,
            "disagree_count": dcount,
            "disagree_rate": round(rate, 4) if rate is not None else None,
            "threshold": DISAGREE_MAX,
            "pass": passed,
            "action": ACTION_PASS if passed else ACTION_RELABEL,
            # —— 以下是给复核人看的补充字段，不参与判定 ——
            "annotated_questions": len(annotated),
            "single_annotated_questions": len([q for q in ann["single"] if by_id[q]["dim"] == d]),
            "data_status": _data_status(d, by_id, ann, ann_rows),
        }

    # ---- 每维锚定审计命中率 ----
    audit = {}
    for d in dims:
        qs = [q for q, rec in audit_q.items() if rec["dimension"] == d]
        sampled = len(qs)
        hit_count = sum(1 for q in qs if audit_q[q]["hit"])
        rate = (hit_count / sampled) if sampled else None
        rules = sorted({audit_q[q]["hit_rule"] for q in qs if audit_q[q]["hit_rule"]})
        if not sampled:
            rule = None
        elif len(rules) == 1:
            rule = rules[0]
        else:
            rule = "mixed(" + ",".join(rules) + ")"
        passed = None if not sampled else bool(rate >= AUDIT_MIN)
        audit[d] = {
            "sampled": sampled,
            "hit_count": hit_count,
            "hit_rate": round(rate, 4) if rate is not None else None,
            "threshold": AUDIT_MIN,
            "pass": passed,
            "action": ACTION_NO_AUDIT if passed is None else (ACTION_PASS if passed else ACTION_REWRITE),
            "hit_rule": rule,
            # —— 补充字段 ——
            "sample_target": AUDIT_SAMPLE_PER_DIM,
            "sample_complete": sampled >= AUDIT_SAMPLE_PER_DIM,
            "mixed_questions": sorted(q for q in qs if audit_q[q]["mixed"]),
        }
        if sampled > AUDIT_SAMPLE_PER_DIM:
            warnings.append("%s 维审计题数 %d 超过规程的每维 %d 题，超出部分一并计入" % (
                d, sampled, AUDIT_SAMPLE_PER_DIM))

    # ---- 总判定 ----
    rework_dims = []
    for d in dims:
        if per_dimension[d]["pass"] is False:
            rework_dims.append({"dimension": d, "reason": "分歧率超线", "action": ACTION_RELABEL})
        if audit[d]["pass"] is False:
            rework_dims.append({"dimension": d, "reason": "锚定审计命中率不足", "action": ACTION_REWRITE})
    overall = OVERALL_REWORK if rework_dims else OVERALL_PASS
    # 阈值判定照抄规程，不改；但「数据不齐时得出的通过」不等于「真的通过」，
    # 另起一个 overall_provisional 标记，避免半份数据被当成整份结论。
    inc_dims = [d for d in dims if per_dimension[d]["data_status"] != "完整"]
    no_audit_dims = [d for d in dims if audit[d]["pass"] is None]
    thin_audit_dims = [d for d in dims if audit[d]["pass"] is not None
                       and not audit[d]["sample_complete"]]
    provisional_reasons = []
    if inc_dims:
        provisional_reasons.append("标注数据不全的维：%s" % "、".join(inc_dims))
    if no_audit_dims:
        provisional_reasons.append("没做锚定审计的维：%s" % "、".join(no_audit_dims))
    if thin_audit_dims:
        provisional_reasons.append("审计抽样不足 %d 题的维：%s" % (
            AUDIT_SAMPLE_PER_DIM, "、".join(thin_audit_dims)))
    overall_provisional = bool(provisional_reasons)

    # ---- rationale 写回建议（只建议，不写库）----
    rationale_suggestions = []
    for d in disputes:
        if d["need_arbitration"]:
            rationale_suggestions.append({
                "qid": d["qid"], "dimension": d["dimension"],
                "reason": "【待仲裁】分歧题尚未给出仲裁结论与理由；仲裁后把理由写回题库 rationale",
                "source": "arbitration", "need_arbitration": True,
            })
        else:
            reason = d["reason"] or ""
            rationale_suggestions.append({
                "qid": d["qid"], "dimension": d["dimension"],
                "reason": reason if reason else "【仲裁理由待补】仲裁表未写理由，请补写后写回题库 rationale",
                "source": "arbitration", "need_arbitration": False,
            })
    for qid, item in by_id.items():
        if not (item.get("rationale") or "").strip():
            rationale_suggestions.append({
                "qid": qid, "dimension": item["dim"],
                "reason": "题库 rationale 为空，需补写判据句",
                "source": "missing_rationale", "need_arbitration": False,
            })
    for qid, rec in sorted(audit_q.items()):
        if not rec["hit"]:
            rationale_suggestions.append({
                "qid": qid, "dimension": rec["dimension"],
                "reason": "锚定审计未命中（换位后没再选中同一行为），该题判据句需重写后写回 rationale",
                "source": "audit_miss", "need_arbitration": False,
            })
    rationale_suggestions.sort(key=lambda x: (x["dimension"], x["qid"], x["source"]))

    # ---- 输入摘要 ----
    annotated_qids = _annotated_qids(ann_rows)
    # 「缺失标注」= 题库里双人标注不齐的题号（完全没标 + 只来了一名标注员）
    missing_annotations = sorted(
        q for q in by_id
        if by_id[q]["dim"] in dims and len(_annots_of(ann_rows, q)) < 2)
    input_summary = {
        "source_files": source_files or {},
        "data_kind": data_kind,
        "annotation_rows": len(ann_rows),
        "arbitration_rows": len(arb_rows),
        "audit_rows": audit_rows_read,
        "items_total": len(items),
        "dimensions": len(dims),
        "dimension_keys": list(dims),
        "annotated_questions": len([q for q in annotated_qids if q in by_id]),
        "fully_annotated_questions": len([
            q for q in annotated_qids if q in by_id and len(_annots_of(ann_rows, q)) >= 2]),
        "single_annotated_questions": len(ann["single"]),
        "single_annotated_qids": sorted(ann["single"]),
        "conflicting_questions": sorted({c["qid"] for c in ann["conflicts"]}),
        "missing_annotations": missing_annotations,
        "unannotated_questions": len([q for q in by_id if q not in annotated_qids]),
        "questions_outside_bank": sorted(set(ann["extra_qids"])),
        "dispute_questions": len(disputes),
        "arbitrated_disputes": len([d for d in disputes if not d["need_arbitration"]]),
        "pending_arbitration": len([d for d in disputes if d["need_arbitration"]]),
        "audit_questions": len(audit_q),
        "audit_mixed_questions": sorted(q for q, r in audit_q.items() if r["mixed"]),
    }

    for d in dims:
        st = per_dimension[d]["data_status"]
        if st != "完整":
            warnings.append("%s 维标注数据%s，分歧率结论需人工复核（判定口径照旧，未改）" % (d, st))
        if audit[d]["pass"] is None:
            warnings.append("%s 维没有锚定审计数据，本维度未参与审计判定" % d)

    return {
        "tool": "analyze_annotations.py",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_kind": data_kind,
        "overall": overall,
        "overall_provisional": overall_provisional,
        "overall_provisional_reasons": provisional_reasons,
        "overall_note": _overall_note(overall, rework_dims, per_dimension, audit, dims),
        "rework_dimensions": rework_dims,
        "thresholds": {
            "disagree_rate_max": DISAGREE_MAX,
            "audit_hit_rate_min": AUDIT_MIN,
            "audit_sample_per_dim": AUDIT_SAMPLE_PER_DIM,
            "source": "pilot/真人试测作业包_20261024.md §五 / §七",
        },
        "hit_rule_desc": HIT_RULE_DESC,
        "input_summary": input_summary,
        "per_dimension": per_dimension,
        "disputes": disputes,
        "audit": audit,
        "audit_questions": {q: audit_q[q] for q in sorted(audit_q)},
        "rationale_suggestions": rationale_suggestions,
        "warnings": warnings,
    }


def _annots_of(ann_rows, qid):
    """某题出现过的标注员代号集合（去重）。"""
    out = []
    for r in ann_rows:
        if r.get("qid") == qid and r.get("annotator") and r["annotator"] not in out:
            out.append(r["annotator"])
    return out


def _annotated_qids(ann_rows):
    """标注表里出现过的题号集合（与题库无关，题库外的另算）。"""
    return {r.get("qid") for r in ann_rows if r.get("qid")}


def _data_status(dim, by_id, ann, ann_rows):
    """该维标注数据状态：完整 / 不全 / 缺失（只作提示，不参与判定）。"""
    qs = [q for q, it in by_id.items() if it["dim"] == dim]
    conflicts = {c["qid"] for c in ann["conflicts"]}
    too_many = set(ann["too_many"])
    complete = 0
    for q in qs:
        if q in conflicts or q in too_many:
            continue
        if len(_annots_of(ann_rows, q)) >= 2:
            complete += 1
    if complete == len(qs):
        return "完整"
    if complete == 0:
        return "缺失"
    return "不全"


def _overall_note(overall, rework_dims, per_dimension, audit, dims):
    """总判定的一句话说明。

    阈值判定照抄规程（不改），但「数据不齐时的通过」不等于「真的通过」——
    分歧率 0% 也可能只是「没人标」。这句话要把这件事说清楚。
    """
    if rework_dims:
        bits = ["%s 维%s（处置：%s）" % (r["dimension"], r["reason"], r["action"])
                for r in rework_dims]
        note = "%s" % "；".join(bits)
    else:
        note = "四维的分歧率与锚定审计命中率均已过线"
    incomplete = [d for d in dims if per_dimension[d]["data_status"] != "完整"]
    no_audit = [d for d in dims if audit[d]["pass"] is None]
    thin_audit = [d for d in dims if audit[d]["pass"] is not None
                   and not audit[d]["sample_complete"]]
    tail = []
    if incomplete:
        tail.append("标注数据不全的维：%s" % "、".join(incomplete))
    if no_audit:
        tail.append("没有锚定审计数据的维：%s" % "、".join(no_audit))
    if thin_audit:
        tail.append("审计抽样不足 6 题的维：%s" % "、".join(thin_audit))
    if tail:
        note += "。⚠ **本结论暂定**：%s —— 分歧率 0%% 也可能只是「没人标」而不是「标了都对」；"                 "这些维的结论需人工复核或补齐数据后再判（判定口径未改）" % "；".join(tail)
    return note


# ------------------------------------------------------------- 人读版报告
def render_markdown(rep):
    """生成可直接贴进试测报告的人读版。"""
    L = []
    is_selftest = rep.get("data_kind") == "selftest"
    L.append("# 真人试测：双人标注与锚定审计判定报告")
    L.append("")
    if is_selftest:
        L.append("> ⚠ **本报告由 `--selftest` 生成，数据是自检 fixture，不是真人试测数据。"
                 "禁止当作试测结论引用。**")
        L.append("")
    L.append("> 生成时间：%s ｜ 工具：`pilot/analyze_annotations.py` ｜ 数据性质：%s" % (
        rep["generated_at"], "自检（非真人数据）" if is_selftest else "真人标注数据"))
    src = rep["input_summary"].get("source_files", {})
    if src:
        L.append(">")
        L.append("> 数据来源：标注 `%s` ｜ 仲裁 `%s` ｜ 审计 `%s`" % (
            src.get("annotations") or "—",
            src.get("arbitration") or "（未提供）",
            src.get("audit") or "（未提供）"))
    L.append("")

    # ---- 顶部总判定 ----
    L.append("## 总判定")
    L.append("")
    L.append("**%s** —— %s" % (rep["overall"], rep["overall_note"]))
    L.append("")
    if rep.get("overall_provisional"):
        L.append("> ⚠ **结论暂定，不能当最终结论用。** 原因：%s" % "；".join(
            rep.get("overall_provisional_reasons") or []))
        L.append(">")
        L.append("> 分歧率 0% 也可能只是「没人标」而不是「标了都对」。"
                 "先把数据补齐再判，判定口径本身没有改。")
        L.append(">")
    L.append("")
    L.append("判定阈值（照抄 `%s`，本报告不临时改口径）：双人标注分歧率 ≤ %.0f%% ｜ "
             "锚定审计命中率 ≥ %.0f%%（每维抽 %d 题）" % (
                 rep["thresholds"]["source"], rep["thresholds"]["disagree_rate_max"] * 100,
                 rep["thresholds"]["audit_hit_rate_min"] * 100,
                 rep["thresholds"]["audit_sample_per_dim"]))
    L.append("")

    # ---- 一、分歧率 ----
    L.append("## 一、双人标注分歧率（阈值 ≤ %.0f%%）" % (DISAGREE_MAX * 100))
    L.append("")
    L.append("| 维度 | 题数 | 分歧数 | 分歧率 | 判定 | 处置 | 标注数据 |")
    L.append("|---|---|---|---|---|---|---|")
    for d, r in rep["per_dimension"].items():
        if r["pass"] and r["data_status"] != "完整":
            verdict = "暂定过线"
        else:
            verdict = "过线" if r["pass"] else "不过线"
        L.append("| %s | %d | %d | %s | %s | %s | %s |" % (
            d, r["total"], r["disagree_count"], pct(r["disagree_rate"]), verdict,
            ACTION_LABEL.get(r["action"], r["action"]), r["data_status"]))
    L.append("")
    L.append("> 处置口径：分歧率 > %.0f%% → **该维整维重标**（不是只改分歧题）。" % (DISAGREE_MAX * 100))
    L.append("")

    # ---- 二、锚定审计 ----
    L.append("## 二、锚定审计命中率（阈值 ≥ %.0f%%）" % (AUDIT_MIN * 100))
    L.append("")
    L.append("| 维度 | 抽检题数 | 命中题数 | 命中率 | 判定 | 处置 | 判定口径 hit_rule |")
    L.append("|---|---|---|---|---|---|---|")
    for d, r in rep["audit"].items():
        if r["pass"] is None:
            verdict = "未审计"
        elif r["pass"] and not r["sample_complete"]:
            verdict = "暂定过线"
        else:
            verdict = "过线" if r["pass"] else "不过线"
        L.append("| %s | %d | %d | %s | %s | %s | %s |" % (
            d, r["sampled"], r["hit_count"], pct(r["hit_rate"]),
            verdict, ACTION_LABEL.get(r["action"], r["action"]), r["hit_rule"] or "—"))
    L.append("")
    L.append("> 判定口径说明：")
    for k, v in rep["hit_rule_desc"].items():
        L.append("> - `%s`：%s" % (k, v))
    mixed = rep["input_summary"].get("audit_mixed_questions") or []
    if mixed:
        L.append(">")
        L.append("> ⚠ 以下题目两名标注员判定不一致（一人命中一人未命中），本报告按「未命中」计，"
                 "请人工复核：%s" % "、".join(mixed))
    L.append("")

    # ---- 三、分歧题 ----
    L.append("## 三、分歧题清单（共 %d 题）" % len(rep["disputes"]))
    L.append("")
    if rep["disputes"]:
        L.append("| 题号 | 维度 | 标注员 A | 标注员 B | 标注员备注 | 仲裁结果 | 仲裁理由 | 待仲裁 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for d in rep["disputes"]:
            cm = "；".join(x for x in (d.get("comment_a", ""), d.get("comment_b", "")) if x)
            L.append("| %s | %s | %s（选 %s） | %s（选 %s） | %s | %s | %s | %s |" % (
                d["qid"], d["dimension"], d["annotator_a"], d["choice_a"],
                d["annotator_b"], d["choice_b"], cm or "—",
                d["final_choice"] or "—", d["reason"] or "—",
                "是" if d["need_arbitration"] else "否"))
    else:
        L.append("（无分歧题）")
    L.append("")

    pending = [d for d in rep["disputes"] if d["need_arbitration"]]
    L.append("## 四、待仲裁题（共 %d 题）" % len(pending))
    L.append("")
    if pending:
        L.append("| 题号 | 维度 | 标注员 A | 标注员 B |")
        L.append("|---|---|---|---|")
        for d in pending:
            L.append("| %s | %s | %s（选 %s） | %s（选 %s） |" % (
                d["qid"], d["dimension"], d["annotator_a"], d["choice_a"],
                d["annotator_b"], d["choice_b"]))
        L.append("")
        L.append("> 仲裁权在测评负责人；仲裁理由写回题库 `rationale`，本工具不代劳。")
    else:
        L.append("（全部分歧题均已仲裁）")
    L.append("")

    # ---- 五、rationale 写回建议 ----
    L.append("## 五、题库 `rationale` 写回建议（共 %d 条 · **机器不写库**）" % len(rep["rationale_suggestions"]))
    L.append("")
    if rep["rationale_suggestions"]:
        L.append("| 题号 | 维度 | 来源 | 建议写回 rationale 的理由 |")
        L.append("|---|---|---|---|")
        for s in rep["rationale_suggestions"]:
            L.append("| %s | %s | %s | %s |" % (
                s["qid"], s["dimension"], s.get("source", "-"), s["reason"]))
        L.append("")
        L.append("> 来源：`arbitration` = 分歧题仲裁理由；`missing_rationale` = 题库理由为空；"
                 "`audit_miss` = 锚定审计未命中、判据句需重写。")
    else:
        L.append("（无）")
    L.append("")

    # ---- 六、数据完整性 ----
    s = rep["input_summary"]
    L.append("## 六、输入与数据完整性")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append("| 标注表读入行数 | %d |" % s["annotation_rows"])
    L.append("| 仲裁表读入行数 | %d |" % s["arbitration_rows"])
    L.append("| 审计表读入行数 | %d |" % s["audit_rows"])
    L.append("| 题库题数 | %d |" % s["items_total"])
    L.append("| 维度数 | %d（%s） |" % (s["dimensions"], "、".join(s["dimension_keys"])))
    L.append("| 有标注的题数 | %d |" % s["annotated_questions"])
    L.append("| 双人标注齐全的题数 | %d |" % s["fully_annotated_questions"])
    L.append("| 只来了一名标注员的题数 | %d |" % s["single_annotated_questions"])
    L.append("| 分歧题数 | %d |" % s["dispute_questions"])
    L.append("| 已仲裁 / 待仲裁 | %d / %d |" % (s["arbitrated_disputes"], s["pending_arbitration"]))
    L.append("| 审计覆盖题数 | %d |" % s["audit_questions"])
    L.append("")
    if s["missing_annotations"]:
        L.append("**缺失标注的题号（%d 题 · 双人标注不齐）**：%s" % (
            len(s["missing_annotations"]), "、".join(s["missing_annotations"])))
        L.append("")
        L.append("> 其中完全没标 %d 题、只来了一名标注员 %d 题；这些题不计入分歧数，"
                 "所在维的分歧率结论需人工复核。" % (
                     s["unannotated_questions"], s["single_annotated_questions"]))
    else:
        L.append("**缺失标注的题号**：无（96 题双人标注齐全）")
    L.append("")
    if s["questions_outside_bank"]:
        L.append("**标注表中题库外的题号**：%s" % "、".join(s["questions_outside_bank"]))
        L.append("")

    if rep["warnings"]:
        L.append("## 七、数据告警（供复核）")
        L.append("")
        for w in rep["warnings"]:
            L.append("- %s" % w)
        L.append("")

    L.append("---")
    L.append("")
    L.append("本报告由 `pilot/analyze_annotations.py` 生成，判定口径见 "
             "`pilot/analyze_annotations_说明.md`。机器只判定，不裁决。")
    L.append("")
    return "\n".join(L)


# ------------------------------------------------------------------ 自检
def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def build_selftest_fixture(items, by_id, tmpdir):
    """造自检 fixture。

    三种情形（题号、标注员代号、文件名一律带 SELFTEST_ 标记，一眼看出不是真人数据）：
      1. 两维分歧率超线：INT 4/24、TFS 5/24 → 整维重标
      2. 审计命中率达线：SNT 6/6 → 通过；JPS 4/6 → 该维题目重写
      3. 缺仲裁：部分分歧题不给仲裁 → final_choice 为 null、need_arbitration 为 true
    """
    by_dim = {}
    for it in items:
        by_dim.setdefault(it["dim"], []).append(it)
    ann_rows = []
    arb_rows = []
    aud_rows = []

    # 造分歧：INT 前 4 题、TFS 前 5 题，两名标注员选到不同侧
    disagree_plan = {"INT": 4, "TFS": 5}
    for dim, n in disagree_plan.items():
        for it in by_dim[dim][:n]:
            other = "b" if it["anchor"] == "a" else "a"
            ann_rows.append([it["id"], "SELFTEST_A", it["anchor"], "自检数据"])
            ann_rows.append([it["id"], "SELFTEST_B", other, "自检数据"])
    # 其余题两名标注员一致
    for dim, its in by_dim.items():
        for it in its:
            if it["id"] in {r[0] for r in ann_rows}:
                continue
            ann_rows.append([it["id"], "SELFTEST_A", it["anchor"], "自检数据"])
            ann_rows.append([it["id"], "SELFTEST_B", it["anchor"], "自检数据"])

    # 仲裁：只给两题，其余分歧题故意缺仲裁
    for qid in ("INT-02", "TFS-03"):
        arb_rows.append([qid, "a", "自检：仲裁理由占位"])
    # 仲裁表里再放一条非法取值，验证「取值非法不当成仲裁」
    arb_rows.append(["INT-03", "?", "自检：非法取值，应被忽略"])

    # 审计：SNT 6 题全命中；JPS 6 题命中 4 题
    for dim, hit_n in (("SNT", 6), ("JPS", 4)):
        for i, it in enumerate(by_dim[dim][:6]):
            swapped = "b" if it["anchor"] == "a" else "a"
            choice = swapped if i < hit_n else it["anchor"]
            aud_rows.append([it["id"], it["anchor"], swapped, "SELFTEST_A", choice])
            aud_rows.append([it["id"], it["anchor"], swapped, "SELFTEST_B", choice])

    paths = {
        "annotations": os.path.join(tmpdir, "SELFTEST_annotations.csv"),
        "arbitration": os.path.join(tmpdir, "SELFTEST_arbitration.csv"),
        "audit": os.path.join(tmpdir, "SELFTEST_audit.csv"),
    }
    _write_csv(paths["annotations"], ANN_COLS + ANN_OPT, ann_rows)
    _write_csv(paths["arbitration"], ARB_COLS + ARB_OPT, arb_rows)
    _write_csv(paths["audit"], AUD_COLS, aud_rows)
    return paths


def selftest():
    """自检：造 fixture → 跑判定 → 断言结论正确。所有临时文件都在 tempfile 目录内。"""
    items, by_id, dims = load_items()
    out_before = _snapshot(OUT)
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print("  [ok] %s" % name)
        else:
            print("  [FAIL] %s %s" % (name, detail))
            failures.append(name)

    with tempfile.TemporaryDirectory(prefix="dsh_annotations_selftest_") as tmpdir:
        paths = build_selftest_fixture(items, by_id, tmpdir)
        ann_rows, _ = read_csv_rows(paths["annotations"], ANN_COLS, "标注表", ANN_OPT)
        arb_rows, _ = read_csv_rows(paths["arbitration"], ARB_COLS, "仲裁表", ARB_OPT)
        aud_rows, _ = read_csv_rows(paths["audit"], AUD_COLS, "审计表")
        rep = build_report(ann_rows, arb_rows, aud_rows, items, by_id, dims,
                           source_files=paths, data_kind="selftest")

        outdir = os.path.join(tmpdir, "out")
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "annotations_report.json"), "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
        with open(os.path.join(outdir, "annotations_report.md"), "w", encoding="utf-8") as f:
            f.write(render_markdown(rep))

        pd = rep["per_dimension"]
        ad = rep["audit"]

        print("== 自检 1：两维分歧率超线 → 整维重标 ==")
        check("INT 分歧 4/24 = 16.7% > 15% → 不过线",
              pd["INT"]["disagree_count"] == 4 and pd["INT"]["disagree_rate"] > DISAGREE_MAX
              and pd["INT"]["pass"] is False,
              "实际 %s" % pd["INT"])
        check("INT 处置 = 整维重标", pd["INT"]["action"] == ACTION_RELABEL, pd["INT"]["action"])
        check("TFS 分歧 5/24 = 20.8% > 15% → 不过线",
              pd["TFS"]["disagree_count"] == 5 and pd["TFS"]["pass"] is False,
              "实际 %s" % pd["TFS"])
        check("TFS 处置 = 整维重标", pd["TFS"]["action"] == ACTION_RELABEL, pd["TFS"]["action"])
        check("SNT 分歧 0/24 → 过线",
              pd["SNT"]["disagree_count"] == 0 and pd["SNT"]["pass"] is True,
              "实际 %s" % pd["SNT"])

        print("== 自检 2：锚定审计命中率判定 ==")
        check("SNT 审计 6 题全命中 → 命中率 100% ≥ 80% → 过线",
              ad["SNT"]["sampled"] == 6 and ad["SNT"]["hit_count"] == 6
              and ad["SNT"]["hit_rate"] == 1.0 and ad["SNT"]["pass"] is True,
              "实际 %s" % ad["SNT"])
        check("SNT 处置 = pass", ad["SNT"]["action"] == ACTION_PASS, ad["SNT"]["action"])
        check("JPS 审计命中 4/6 = 66.7% < 80% → 不过线",
              ad["JPS"]["sampled"] == 6 and ad["JPS"]["hit_count"] == 4
              and ad["JPS"]["pass"] is False, "实际 %s" % ad["JPS"])
        check("JPS 处置 = 该维题目重写", ad["JPS"]["action"] == ACTION_REWRITE, ad["JPS"]["action"])
        check("审计 hit_rule 已记录", ad["SNT"]["hit_rule"] == HIT_RULE_SIDE, ad["SNT"]["hit_rule"])

        print("== 自检 3：缺仲裁 → final_choice 为 null、need_arbitration 为 true ==")
        dis = {d["qid"]: d for d in rep["disputes"]}
        check("INT-01 无仲裁 → final_choice is None",
              dis["INT-01"]["final_choice"] is None, dis["INT-01"])
        check("INT-01 need_arbitration is True",
              dis["INT-01"]["need_arbitration"] is True, dis["INT-01"])
        check("INT-02 有仲裁 → final_choice = a、reason 非空",
              dis["INT-02"]["final_choice"] == "a" and bool(dis["INT-02"]["reason"]),
              dis["INT-02"])
        check("INT-03 仲裁取值非法 → 按未仲裁处理",
              dis["INT-03"]["final_choice"] is None and dis["INT-03"]["need_arbitration"] is True,
              dis["INT-03"])
        check("待仲裁题数 = 9 - 2 = 7（INT-02、TFS-03 已仲裁）",
              rep["input_summary"]["pending_arbitration"] == 7,
              rep["input_summary"]["pending_arbitration"])
        check("分歧题总数 = 9", rep["input_summary"]["dispute_questions"] == 9,
              rep["input_summary"]["dispute_questions"])

        print("== 自检 4：总判定与写回建议 ==")
        check("overall = 需返工", rep["overall"] == OVERALL_REWORK, rep["overall"])
        qids = {s["qid"] for s in rep["rationale_suggestions"]}
        check("rationale 建议含已仲裁题 INT-02", "INT-02" in qids, sorted(qids))
        check("rationale 建议含审计未命中题 JPS-05", "JPS-05" in qids, sorted(qids))
        check("rationale 建议含待仲裁题 INT-01", "INT-01" in qids, sorted(qids))
        check("rationale 建议只做建议、不写库（未改题库文件）",
              all("source" in s for s in rep["rationale_suggestions"]))

        print("== 自检 5：命中判定口径（hit_rule）==")
        it = by_id["INT-01"]
        swapped = "b" if it["anchor"] == "a" else "a"
        hit, rule, _ = judge_audit_hit(it, it["anchor"], swapped, swapped)
        check("记侧别字母、选 swapped_anchor → 命中（anchor_side）",
              hit is True and rule == HIT_RULE_SIDE, (hit, rule))
        hit, rule, _ = judge_audit_hit(it, it["anchor"], swapped, it["anchor"])
        check("记侧别字母、选原有效端 → 未命中", hit is False and rule == HIT_RULE_SIDE, (hit, rule))
        hit, rule, _ = judge_audit_hit(it, it["anchor"], swapped, it[it["anchor"]])
        check("记行为原文且是原有效端那条 → 命中（behavior_text）",
              hit is True and rule == HIT_RULE_TEXT, (hit, rule))
        hit, rule, _ = judge_audit_hit(it, it["anchor"], swapped, it[swapped])
        check("记行为原文但是对面那条 → 未命中", hit is False and rule == HIT_RULE_TEXT, (hit, rule))
        hit, rule, note = judge_audit_hit(it, it["anchor"], swapped, "看不懂")
        check("题面判不出 → 退回 fallback_swapped_anchor 且不瞎猜命中",
              hit is False and rule == HIT_RULE_FALLBACK, (hit, rule, note))

        print("== 自检 6：产物与目录纪律 ==")
        check("报告 JSON 已写出", os.path.exists(os.path.join(outdir, "annotations_report.json")))
        check("报告 MD 已写出", os.path.exists(os.path.join(outdir, "annotations_report.md")))
        check("自检产物全部落在 tempfile 目录内",
              all(p.startswith(tmpdir) for p in paths.values()), paths)
        check("pilot/out/ 未被自检写入", _snapshot(OUT) == out_before)

    print("")
    if failures:
        print("自检未通过：%d 项 —— %s" % (len(failures), "、".join(failures)))
        return 1
    print("自检全部通过。")
    return 0


def _snapshot(path):
    """目录内容快照（文件名 + 大小 + mtime），用来验证「自检没往 pilot/out/ 写东西」。"""
    if not os.path.isdir(path):
        return None
    out = {}
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        try:
            st = os.stat(full)
            out[name] = (st.st_size, int(st.st_mtime))
        except OSError:
            out[name] = None
    return out


# --------------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(
        description="真人试测：双人标注 / 仲裁 / 锚定审计的机器判定（票 #26 前置工具）")
    ap.add_argument("--annotations", metavar="CSV",
                    help="双人标注表：qid,annotator,choice,comment")
    ap.add_argument("--arbitration", metavar="CSV",
                    help="仲裁表（可空）：qid,final_choice,reason")
    ap.add_argument("--audit", metavar="CSV",
                    help="锚定审计表（可空）：qid,orig_anchor,swapped_anchor,annotator,choice")
    ap.add_argument("--out-dir", metavar="DIR", help="报告输出目录")
    ap.add_argument("--selftest", action="store_true", help="跑自检（造 fixture 并断言判定）")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    if not args.annotations:
        ap.error("--annotations 必填（--selftest 模式除外）")
    if not args.out_dir:
        ap.error("--out-dir 必填")

    items, by_id, dims = load_items()
    ann_rows, ann_warn = read_csv_rows(args.annotations, ANN_COLS, "标注表", ANN_OPT)
    arb_rows, arb_warn = read_csv_rows(args.arbitration, ARB_COLS, "仲裁表", ARB_OPT)
    aud_rows, _ = read_csv_rows(args.audit, AUD_COLS, "审计表")

    rep = build_report(ann_rows, arb_rows, aud_rows, items, by_id, dims,
                       extra_warnings=ann_warn + arb_warn,
                       source_files={"annotations": os.path.abspath(args.annotations),
                                     "arbitration": os.path.abspath(args.arbitration)
                                                   if args.arbitration else None,
                                     "audit": os.path.abspath(args.audit) if args.audit else None},
                       data_kind="real")

    os.makedirs(args.out_dir, exist_ok=True)
    jpath = os.path.join(args.out_dir, "annotations_report.json")
    mpath = os.path.join(args.out_dir, "annotations_report.md")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    with open(mpath, "w", encoding="utf-8") as f:
        f.write(render_markdown(rep))

    # ------------------------------------------------------------ 打印摘要
    print("== 真人标注判定（总判定：%s）==" % rep["overall"])
    print("输入：标注 %d 行 ｜ 仲裁 %d 行 ｜ 审计 %d 行 ｜ 题库 %d 题 / %d 维" % (
        rep["input_summary"]["annotation_rows"], rep["input_summary"]["arbitration_rows"],
        rep["input_summary"]["audit_rows"], rep["input_summary"]["items_total"],
        rep["input_summary"]["dimensions"]))
    for d in dims:
        p = rep["per_dimension"][d]
        a = rep["audit"][d]
        print("  %s 分歧 %d/%d = %s → %s（%s）｜ 审计 %d/%d = %s → %s（%s）" % (
            d, p["disagree_count"], p["total"], pct(p["disagree_rate"]),
            "过线" if p["pass"] else "不过线", p["action"],
            a["hit_count"], a["sampled"], pct(a["hit_rate"]),
            "未审计" if a["pass"] is None else ("过线" if a["pass"] else "不过线"),
            a["action"]))
    print("分歧题 %d（待仲裁 %d）｜ rationale 写回建议 %d 条（机器不写库）" % (
        rep["input_summary"]["dispute_questions"], rep["input_summary"]["pending_arbitration"],
        len(rep["rationale_suggestions"])))
    if rep.get("overall_provisional"):
        print("⚠ 结论暂定，不能当最终结论用：%s" % "；".join(
            rep.get("overall_provisional_reasons") or []))
    if rep["warnings"]:
        print("告警 %d 条（见报告「数据告警」一节）" % len(rep["warnings"]))
    print("已写出 %s 与 %s" % (jpath, mpath))


if __name__ == "__main__":
    main()
