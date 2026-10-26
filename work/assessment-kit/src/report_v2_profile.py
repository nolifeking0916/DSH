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


def _band(v):
    return ("顶尖" if v >= 85 else "优秀" if v >= 70 else "良好" if v >= 55
            else "合格" if v >= 40 else "待提升")


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


def talent_score(m1, m2, m3):
    """人才综合素质（0–100）与潜力（可达分 / 空间）。"""
    p1 = sum(d["score"] / float(d["max"]) for d in m1["dims"]) / max(1, len(m1["dims"]))
    p2 = float(m2["total"]) / 5.0
    p3 = float(m3["pct"]) / 100.0
    comp = round((p1 + p2 + p3) / 3.0 * 100, 1)
    grade = _band(comp)
    # 潜力：把最短板那一类补到三类平均水平的可达综合分
    parts = {"性格特质": p1, "情绪特质": p2, "逻辑评价": p3}
    short_name = min(parts, key=lambda k: parts[k])
    avg = (p1 + p2 + p3) / 3.0
    lifted = list(parts.values())
    lifted[list(parts).index(short_name)] = avg
    potential = round(sum(lifted) / 3.0 * 100, 1)
    space = round(potential - comp, 1)
    pgrade = _band(potential)
    note_key = "high" if space >= 12 else ("mid" if space >= 6 else "low")
    return {
        "comprehensive": comp, "grade": grade,
        "parts": [{"name": "性格特质", "pct": round(p1 * 100, 1), "basis": "四维命中率平均"},
                  {"name": "情绪特质", "pct": round(p2 * 100, 1), "basis": "加权总分 ÷ 5.00"},
                  {"name": "逻辑评价", "pct": round(p3 * 100, 1), "basis": "参考分布百分位"}],
        "potential": potential, "potential_grade": pgrade, "space": space,
        "short_name": short_name,
        "potential_note": PROFILES["potential_note"][note_key],
        "talent_text": PROFILES["talent"][grade],
    }


def overall_sentence(m1, m2, m3, tp, an, ta):
    """整体画像一句话：性格特质 + 情绪特质 + 逻辑评价。"""
    p = PROFILES["m2_summary"].get(m2["grade"], "")
    l = PROFILES["m3_summary"].get(m3["grade"], "")
    return ("性格上属于%s（%s），%s；情绪上%s；逻辑上%s"
            % (tp["type_name"] or "未定型", tp["code"], tp["type_desc"], p, l))
