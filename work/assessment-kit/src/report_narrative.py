#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判读话术库 + 可信度（施测人报告用）。

两件事：
1. **话术**：把候选人的分数画像变成文字。规则存在**云上数据库** public.report_narrative
   （维度 × 分数档 × 特征极 ⇒ 一段话术），由云函数按分数匹配后下发；
   云端取不到时用仓内快照 data/narrative_rules.json + 同一套匹配逻辑兜底（离线可用）。
2. **可信度**：回答「这份结果能不能信」。三个信号：
   · 同侧作答（人格特质 96 题的两极选择）—— 连续同侧越多、总体越偏，越像乱答；
   · 缺失率 —— 未作答的题越多，结果越不可靠；
   · 一致性题（情景处理里 12 对同一情境的相反问法）—— 两可情境下选向不一致，说明倾向不稳。
   再加一条粗信号：总作答时长（秒/题）异常偏快或偏慢。

用法：
    from report_narrative import build_profile, fetch_narrative, credibility
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "data", "narrative_rules.json")
ENDPOINT = os.environ.get(
    "ASSESSMENT_API",
    "https://uu-one-d4gc4ot78a702cb70-1257197409.ap-shanghai.app.tcloudbase.com/api/assessment",
)

BANDS = ["顶尖", "优秀", "良好", "合格", "待提升"]
MODULES = {"m1": "personality", "m2": "situation", "m3": "reasoning"}


# ---------------------------------------------------------------- 档位
def band_of_ratio(v, lo, hi, reverse=False):
    """按分数占比落到五档。reverse=True 时分数越高档越低（用于错误率类）。"""
    r = (v - lo) / float(hi - lo) if hi > lo else 0.0
    r = max(0.0, min(1.0, r))
    if reverse:
        r = 1.0 - r
    if r >= 0.85:
        return "顶尖"
    if r >= 0.70:
        return "优秀"
    if r >= 0.55:
        return "良好"
    if r >= 0.40:
        return "合格"
    return "待提升"


def band_of_score(v, lo, hi, reverse=False):
    return band_of_ratio(v, lo, hi, reverse)


# ---------------------------------------------------------------- 画像
def build_profile(data, m1, m2, m3, compose, m1_raw=None):
    """分数画像：报告与话术匹配的输入。

    personality：四个维度各自的分数档 + **偏向哪一极**（a/b）。
                 极的判定用 m1_raw：某维 24 题里选 a 的比例 > 60% ⇒ 偏 a 端。
    situation / reasoning：每个维度的分数档。
    overall：综合档 + 要哪几类话术。
    """
    prof = {"personality": {}, "situation": {}, "reasoning": {},
            "overall": {"grade": compose.get("grade"),
                        "kinds": ["profile", "fit", "potential", "strength", "caution",
                                  "conclusion", "boundary", "method"]}}

    # 人格特质：分数档 + 偏向极
    # ⚠️ 题库里同一维度的 a/b 两列是**正反混排**的（有的题 a 端是「主动」，有的题 a 端是「等待」），
    #    所以「偏向哪一极」不能按 a/b 列的占比算，必须按**每题的锚定端**算：
    #    答在锚定端（更有效的一端）⇒ 落在该维的 a 极；答在另一端 ⇒ b 极。
    #    这一列的计数其实就等于该维得分（得分 = 答在锚定端的题数），
    #    极的判定只在「同一档位里挑哪一面的话术」时起作用。
    m1_items = json.load(open(os.path.join(ROOT, "items", "m1_items.json"), encoding="utf-8"))
    order = [it["id"] for it in m1_items["items"]]
    idx_of = {iid: i for i, iid in enumerate(order)}
    dim_items = {}
    for it in m1_items["items"]:
        dim_items.setdefault(it["dim"], []).append(it)
    # 逐题 → 性格两极的映射表（data/m1_pole_map.json）。
    # 没有它就退回「按锚定端判极」——那只是近似：锚定端是「更有效的一端」，
    # 跟性格两极（主动/等待…）不是一回事，题库里 a/b 两列是正反混排的。
    pole_map, pole_src = {}, "anchor"
    pm_path = os.path.join(ROOT, "data", "m1_pole_map.json")
    if os.path.exists(pm_path):
        try:
            pm = json.load(open(pm_path, encoding="utf-8"))
            pole_map = pm.get("items") or {}
            if pole_map:
                pole_src = "map"
        except Exception:
            pole_map = {}
    for d in m1.get("dims", []):
        key = d["key"]
        a_cnt = b_cnt = 0
        if m1_raw:
            for it in dim_items.get(key, []):
                i = idx_of.get(it["id"])
                if i is None or i >= len(m1_raw):
                    continue
                v = m1_raw[i]
                if v is None:
                    continue
                pmv = pole_map.get(it["id"])
                if pmv is not None:
                    # 映射表：pmv = 落在「极 a」的那个选项值
                    if v == int(pmv):
                        a_cnt += 1
                    else:
                        b_cnt += 1
                else:
                    ans_is_a = (v == 0)
                    anchor_is_a = (str(it.get("anchor") or "a").lower() != "b")
                    if ans_is_a == anchor_is_a:
                        a_cnt += 1
                    else:
                        b_cnt += 1
        total = a_cnt + b_cnt
        pole = "a" if (total == 0 or a_cnt >= b_cnt) else "b"
        prof["personality"][key] = {"dimension": key, "score": d["score"], "max": d.get("max", 24),
                                    "band": d["grade"], "pole": pole,
                                    "a_cnt": a_cnt, "b_cnt": b_cnt, "pole_src": pole_src,
                                    "aligned": (round(a_cnt / float(total), 3) if total else None)}

    # 报告侧的 m2 维度只有名字没有 key ⇒ 用题库的 名字→key 映射补上
    eq = json.load(open(os.path.join(ROOT, "data", "eq_bank_encoded.json"), encoding="utf-8"))
    key_of_name = {x.get("name"): x.get("key") for x in (eq.get("dimensions") or [])}
    for d in m2.get("dims", []):
        k = d.get("key") or key_of_name.get(d.get("name")) or d.get("name")
        prof["situation"][k] = {"dimension": k, "name": d.get("name"),
                                "score": d["score"], "max": d.get("max", 12),
                                "band": d["grade"], "flag": d.get("flag")}
    for d in m3.get("dims", []):
        rate = d.get("rate", 0)
        prof["reasoning"][d["key"]] = {"dimension": d["key"], "rate": rate,
                                       "correct": d.get("correct"), "total": d.get("total"),
                                       "band": d.get("grade") or band_of_ratio(rate, 0, 100)}
    return prof


# ---------------------------------------------------------------- 匹配（本地兜底）
def _pick(rules, module, dimension, band, pole, kind=None):
    cands = [r for r in rules
             if r.get("module") == module and r.get("dimension") == dimension
             and (kind is None or r.get("kind") == kind)]
    tries = []
    if band and band != "__all__":
        tries.append((band, pole or "__any__"))
        tries.append((band, "__any__"))
    tries.append(("__all__", "__any__"))
    for b, p in tries:
        for r in cands:
            if r.get("band") == b and r.get("pole", "__any__") == p:
                return r
    return None


def match_local(rules, profile):
    out = {"personality": {}, "situation": {}, "reasoning": {}, "overall": []}
    for key, d in (profile.get("personality") or {}).items():
        r = _pick(rules, "personality", d.get("dimension", key), d.get("band"), d.get("pole"))
        if r:
            out["personality"][key] = {"text": r["text"], "title": r.get("title"),
                                        "pole_label": r.get("pole_label"),
                                        "band": d.get("band"), "pole": d.get("pole")}
    for key, d in (profile.get("situation") or {}).items():
        r = _pick(rules, "situation", d.get("dimension", key), d.get("band"), None)
        if r:
            out["situation"][key] = {"text": r["text"], "title": r.get("title"), "band": d.get("band")}
    for key, d in (profile.get("reasoning") or {}).items():
        r = _pick(rules, "reasoning", d.get("dimension", key), d.get("band"), None)
        if r:
            out["reasoning"][key] = {"text": r["text"], "title": r.get("title"), "band": d.get("band")}
    ov = profile.get("overall") or {}
    for kind in (ov.get("kinds") or []):
        r = _pick(rules, "overall", "__overall__", ov.get("grade"), "__any__", kind)
        if r:
            out["overall"].append({"kind": kind, "title": r.get("title"), "text": r["text"]})
    return out


def load_local_rules():
    if not os.path.exists(RULES_PATH):
        return []
    try:
        return json.load(open(RULES_PATH, encoding="utf-8")).get("rules", [])
    except Exception:
        return []


def fetch_narrative(profile, timeout=12):
    """先问云上（规则库在库里，匹配也在服务端做）；取不到就用本地快照兜底。"""
    try:
        q = urllib.parse.quote(json.dumps(profile, ensure_ascii=False))
        req = urllib.request.Request(ENDPOINT + "?action=narrative&profile=" + q,
                                     headers={"User-Agent": "report-narrative"})
        j = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore"))
        if j.get("ok") and j.get("narrative"):
            nar = j["narrative"]
            if nar.get("personality") or nar.get("situation") or nar.get("reasoning") or nar.get("overall"):
                nar["source"] = "cloud"
                return nar
    except Exception:
        pass
    nar = match_local(load_local_rules(), profile)
    nar["source"] = "local"
    return nar


# ---------------------------------------------------------------- 可信度
def _as_list(v):
    """云端存下来的 m2_answers 是 {"0":0,"1":2,…} 这种对象 ⇒ 统一成按序的列表。"""
    if v is None:
        return []
    if isinstance(v, dict):
        out = []
        for k in sorted(v.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
            out.append(v[k])
        return out
    return list(v)


def _max_run(seq):
    best = cur = 0
    prev = None
    for v in seq:
        if v is None:
            cur = 0
            prev = None
            continue
        if v == prev:
            cur += 1
        else:
            cur = 1
            prev = v
        best = max(best, cur)
    return best


def credibility(data, m1, m2, m3, m1_raw=None, m2_answers=None, m3_answers=None):
    """每个模块一个可信度等级（高 / 中 / 低）+ 依据。

    信号与门槛（都写死在这里，报告里只给结论与依据）：
    · 同侧作答：人格特质 96 题里同侧连答 ≥ 25 题，或某一侧占比 ≥ 85% ⇒ 扣分；
    · 缺失率：未作答 ≥ 10% 扣一档，≥ 25% 扣两档；
    · 一致性题：情景处理里成对题同向率 < 60% ⇒ 扣一档；
    · 时长：整卷秒/题 < 8 或 > 120 ⇒ 提示（不扣档，只提示）。
    """
    out = {}
    # 人格特质：同侧作答
    flags = []
    level = "高"
    if m1_raw:
        seq = [v for v in m1_raw]
        run = _max_run(seq)
        ones = sum(1 for v in seq if v == 1)
        zeros = sum(1 for v in seq if v == 0)
        answered = ones + zeros
        dom = max(ones, zeros) / float(answered) if answered else 0
        if run >= 25 or dom >= 0.85:
            level = "低"
            flags.append("96 题里同侧连答最长 %d 题、某一侧占比 %.0f%%，接近连续作答同一端的形态" % (run, dom * 100))
        elif run >= 15 or dom >= 0.70:
            level = "中" if level == "高" else level
            flags.append("同侧连答最长 %d 题、某一侧占比 %.0f%%，作答偏好偏集中" % (run, dom * 100))
    if not m1_raw:
        # 离线 9 字段路径（未留存逐题作答）：按规范 §11.4 判缺，不许默认给「高」。
        # 与 m2(:302-304) / m3(:318-320) 的判缺分支同构；level 只从「高」降到「中」，不覆盖已判的「低」。
        flags.append("本次未留存逐题作答，同侧作答与缺失只能看汇总口径")
        level = "中" if level == "高" else level
    miss1 = data.get("unanswered_m1")
    if isinstance(miss1, int) and miss1 > 0:
        flags.append("第一项有 %d 题未作答" % miss1)
        if miss1 >= 24:
            level = "低"
        elif miss1 >= 10 and level == "高":
            level = "中"
    out["m1"] = {"level": level, "flags": flags}

    # 情景处理：缺失 + 一致性
    flags2 = []
    level2 = "高"
    if m2_answers:
        seq2 = _as_list(m2_answers)
        answered = [v for v in seq2 if v is not None]
        miss = len(seq2) - len(answered)
        if miss:
            flags2.append("有 %d 题未作答" % miss)
            if miss >= 20:
                level2 = "低"
            elif miss >= 8 and level2 == "高":
                level2 = "中"
    # 一致性：服务端算好的结果里有「需复核」的题对 ⇒ 那就是两可情境下选向不一致
    pairs = m2.get("consistency") or []
    if pairs:
        bad = [p for p in pairs if "需复核" in (p.get("status") or "")]
        tot = len(pairs)
        same = tot - len(bad)
        rate = same / float(tot)
        if rate < 0.6:
            level2 = "低" if level2 == "高" else level2
            flags2.append("%d 对一致性题里只有 %d 对同向，两可情境下的倾向偏不稳" % (tot, same))
    if not m2_answers:
        flags2.append("本次未留存逐题作答，缺失只能看汇总口径")
        level2 = "中" if level2 == "高" else level2
    out["m2"] = {"level": level2, "flags": flags2}

    # 逻辑分析能力：缺失 + 速度
    flags3 = []
    level3 = "高"
    if m3_answers:
        miss = len(m3_answers) - sum(1 for v in m3_answers if v is not None)
        if miss:
            flags3.append("有 %d 题未作答" % miss)
            if miss >= 10:
                level3 = "低"
            elif miss >= 4 and level3 == "高":
                level3 = "中"
    else:
        flags3.append("本次未留存逐题作答，缺失与作答模式只能看汇总口径")
        level3 = "中" if level3 == "高" else level3
    out["m3"] = {"level": level3, "flags": flags3}

    dur = data.get("duration_ms")
    speed_note = None
    if isinstance(dur, int) and dur > 0:
        per = dur / 212000.0          # 毫秒 ÷ 212 题 ÷ 1000 ⇒ 秒/题
        if per < 4:
            speed_note = "整卷平均 %.1f 秒/题，节奏偏快" % per
        elif per > 120:
            speed_note = "整卷平均 %.0f 秒/题，节奏偏慢" % per
        else:
            speed_note = "整卷平均 %.1f 秒/题" % per
    order = {"高": 3, "中": 2, "低": 1}
    levels = [out["m1"]["level"], out["m2"]["level"], out["m3"]["level"]]
    overall = min(levels, key=lambda x: order.get(x, 3))
    out["overall"] = {"level": overall, "speed": speed_note,
                      "flags": [f for f in (out["m1"]["flags"] + out["m2"]["flags"] + out["m3"]["flags"])]}
    return out
