#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核心人才三联测试 · 画像引擎（2026-10-26 · 维护者定的报告新结构）

算四件事：
  1. **类型归类**：第一项四维各是一个二元极，映射到通行类型学的四轴记号（E/I、S/N、T/F、J/P），
     给出四字母归类与几句描述。**不是标准 MBTI 测评**（题不同、轴的含义是行为倾向而非心理类型），
     报告里必须写明这一点。
  2. **形象类比**：按（主动/等待）×（事实/趋势）×（收口/随机）取一只动物，并说明为什么像它。
  3. **整体画像一句话**：性格特质 + 情绪特质 + 逻辑评价，串成一句话。
  4. **人才综合素质与潜力给分**：
     - 综合素质分 = 性格面（四维命中率平均）、情绪面（加权总分 / 5）、逻辑面（参考分布百分位）三面归一后等权平均，0–100；
     - 潜力分 = **把最短板那一类补到三类平均水平时的可达综合分**（结构推算，不是预测）。

口径都写进报告正文（report_sections 的 note 块），不藏在代码里。
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROFILES = json.load(open(os.path.join(ROOT, "data", "report_profiles.json"), encoding="utf-8"))

ORDER = ["待提升", "合格", "良好", "优秀", "顶尖"]
# 归类阈值：每维有效端命中**严格过半**（>12/24）算偏 a 侧，否则偏 b 侧。
# ⚠ 这个口径必须与文案库（narrative_rules，按维度+等级+极性选文案）一致，
#   否则同一份报告里「类型归类」与「分项判读」会互相打架。
TILT_MIN = 13


def band3(pct):
    """三档只看占满分的比例（维护者 2026-10-26 裁定）：≥85 突出 / 70-85 常规 / <70 待补。"""
    if pct >= 85:
        return "突出"
    if pct >= 70:
        return "常规"
    return "待补"


def dim_band3(score, mx):
    """维度档：同样只看占满分的比例。"""
    return band3(round(score / float(mx) * 100, 1)) if mx else "待补"


def type_profile(m1):
    """第一项四维 → 四轴 → 四字母归类。"""
    axes = []
    letters = ""
    for d in m1["dims"]:
        a = PROFILES["axes"].get(d["key"]) or {}
        side = "a" if d["score"] >= TILT_MIN else "b"
        info = (a.get(side) or {})
        letter = info.get("letter") or "?"
        letters += letter
        axes.append({
            "key": d["key"], "name": d["name"], "score": d["score"], "max": d["max"],
            "grade": d["grade"], "axis": a.get("axis", ""), "letter": letter,
            "side_label": info.get("label", ""), "desc": info.get("desc", ""),
            "tilt": "偏" + info.get("label", "") if side == "a" else "偏" + ((a.get("b") or {}).get("label", "")),
        })
    t = PROFILES["types"].get(letters) or {}
    # 描述句：四轴各一句 + 类型名
    sent = "、".join("%s偏%s" % (x["name"], x["side_label"]) for x in axes)
    return {"code": letters, "type_name": t.get("name", ""), "type_desc": t.get("desc", ""),
            "axes": axes, "summary": sent}


def animal_profile(m1, m2, m3):
    """按三轴取一只动物，并给出为什么像它（带三类强弱的说明）。"""
    tp = type_profile(m1)
    by = {x["key"]: x for x in tp["axes"]}
    k = "%s_%s_%s" % (by["INT"]["letter"], by["SNT"]["letter"], by["JPS"]["letter"])
    a = PROFILES["animals"].get(k) or {}
    # 强弱：三类等级序数
    def g(grade):
        return ORDER.index(grade) if grade in ORDER else 0
    s1 = g(m1["short"]["grade"]); s2 = g(m2["grade"]); s3 = g(m3["grade"])
    strength = "性格面与逻辑面都靠前" if s1 >= 3 and s3 >= 3 else (
        "情绪面最稳" if s2 >= 3 and s2 >= s1 and s2 >= s3 else
        "情绪面相对吃紧" if s2 <= min(s1, s3) else "三类表现比较均衡")
    return {"key": k, "name": a.get("name", ""), "why": a.get("why", ""), "strength": strength}


def three_band(m1, m2, m3):
    """每一项各自与自己的满分比，分三档；**不做跨项平均、不做加权合成**。

    维护者 2026-10-26 裁定：报告的档位只从「结果本身、分数本身」得出 ——
    每个人类测试的得分除以它自己的满分，得到一个百分比，再按百分比切三档。
    """
    p1 = sum(d["score"] / float(d["max"]) for d in m1["dims"]) / max(1, len(m1["dims"]))
    p2 = float(m2["total"]) / 5.0
    # 逻辑评价用「难度加权答对分 ÷ 40」口径（用户裁定：直接根据满分分成三档）
    p3 = float(m3["total"]) / 40.0
    parts = [
        {"name": "性格特质", "score_text": m1["score_text"], "pct": round(p1 * 100, 1),
         "max_text": "四维 0–24（各维独立，无总档）", "basis": "四维命中率平均 ÷ 24"},
        {"name": "情绪特质", "score_text": "%.2f / 5.00" % m2["total"], "pct": round(p2 * 100, 1),
         "max_text": "0–5.00", "basis": "模块总分 ÷ 5.00"},
        {"name": "逻辑评价", "score_text": "%.1f / 40" % m3["total"], "pct": round(p3 * 100, 1),
         "max_text": "难度加权 0–40", "basis": "难度加权答对分 ÷ 40"},
    ]
    for x in parts:
        x["band"] = band3(x["pct"])
        x["text"] = PROFILES["bands"][x["name"]].get(x["band"], "")
    weak = min(parts, key=lambda x: x["pct"])
    # 提升方向：把最弱的一项补到 85% 需要的增量（只算这一项，不做合成）
    need = max(0.0, round(85.0 - weak["pct"], 1))
    return {"parts": parts, "weakest": weak, "gap_to_top": need,
            "note": PROFILES.get("band_note", "")}


def overall_sentence(m1, m2, m3, tp, an, tb):
    """整体画像一句话：性格特质 + 情绪特质 + 逻辑评价。"""
    tb = tb or {}
    parts = {x["name"]: x for x in (tb.get("parts") or [])}
    p = (parts.get("情绪特质") or {}).get("text", "")
    l = (parts.get("逻辑评价") or {}).get("text", "")
    return ("性格上属于%s（%s），%s；情绪上%s；逻辑上%s"
            % (tp["type_name"] or "未定型", tp["code"], tp["type_desc"], p, l))
