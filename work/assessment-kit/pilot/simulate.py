#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模拟试测样本生成器 —— 票 #24（模拟版）。

这个脚本**不产生信效度证据**。它生成一批合成作答，目的是把「真人试测要用的
分析与判定程序」先跑通一遍，并把每一道验收阈值的判定逻辑先验一遍。

三件事必须分清：
  1. 画像与真值 θ 是**模拟设定**，不是对 HR 群体的实证结论。唯一作用是给合成
     作答一个可控真值，用来检验计分管线能不能把真值还原出来。
  2. α / 分半信度算出来的数字是**生成模型的性质**，不是题目的性质。
  3. 分布、极端题、校准切点同理：它们检验的是「分析与判定程序跑得通、报得出」，
     不是「这批题好不好」。

用法：
    python3 pilot/simulate.py                # 主样本 + 整卷端到端样本
    python3 pilot/simulate.py --selftest     # 额外生成 α 自检对照数据集
产物：
    pilot/out/samples.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")

SEED = 20261024
DIMS = ["INT", "SNT", "TFS", "JPS"]

# ---------------------------------------------------------------- 模拟设定
# 画像 = 一组「假设中的 HR 岗位人群作答倾向」。这不是研究结论，是给合成样本
# 注入真值用的参数表。真值越高 = 越常选「更有效的一端」= 该维得分越高。
PROFILES = {
    "HR专员": {
        "theta": {"INT": 0.35, "SNT": 0.15, "TFS": -0.45, "JPS": -0.60},
        "fake": 0.30,          # 装分倾向基线
        "sd_sens": 0.65,       # 对「听起来更专业的一端」的敏感度
        "note": "事务性强、随大流、易迎合",
    },
    "HR经理": {
        "theta": {"INT": 0.60, "SNT": 0.45, "TFS": 0.25, "JPS": 0.20},
        "fake": 0.18, "sd_sens": 0.50,
        "note": "稳，靠经验判断",
    },
    "HR总监": {
        "theta": {"INT": 0.95, "SNT": 0.75, "TFS": 0.85, "JPS": 0.90},
        "fake": 0.10, "sd_sens": 0.40,
        "note": "强，习惯按标准与节奏推进",
    },
}

# 两组样本，对应票 #24 的施测方案（内部候选人 30–50 + 在职员工 30）
GROUPS = [
    # (组名, 人数, {画像: 人数})
    ("内部候选人", 60, {"HR专员": 26, "HR经理": 24, "HR总监": 10}),
    ("在职员工", 60, {"HR专员": 22, "HR经理": 26, "HR总监": 12}),
]

# 异常作答注入（用来验异常检测器能不能抓到，不是用来评价谁）
ANOMALY_PLAN = [
    ("straight_a", 2),   # 直线作答：一律选 a 侧
    ("straight_b", 2),   # 直线作答：一律选 b 侧
    ("random", 2),       # 快速乱答
    ("perfect", 1),      # 全选锚定端（装分到极致）
    ("fast", 1),         # 正常作答但每题 < 3 秒
]

# -------------------------------------------------- 题面文本的机械特征
# 只做两件事：估「两端措辞的专业感差异」（社会赞许偏差的来源）与「两端对称度」
# （清晰度线索）。词汇表是**设定**，不是对 HR 的测量。
PROF = ["主动", "提前", "负责", "推进", "核实", "讲清", "约定", "排好", "收口", "对齐",
        "计划", "标准", "事实", "复盘", "记录", "确认", "安排", "及时", "清晰", "客观",
        "直接", "先", "会前", "留痕"]
WARM = ["照顾", "体谅", "理解", "感受", "关系", "耐心", "沟通", "协调", "换位", "善意",
        "包容", "体贴", "照顾对方"]
PASSIVE = ["等", "拖", "临时", "被动", "看情况", "随", "再说", "以后", "不管", "忽略", "忘", "漏"]


def count_hits(text, words):
    return sum(text.count(w) for w in words)


def social_desirability(text):
    """专业感/温度感得分：越高越像「大家都会选的那一端」。"""
    n = max(4.0, len(text))
    v = 1.0 * count_hits(text, PROF) + 0.8 * count_hits(text, WARM) - 1.0 * count_hits(text, PASSIVE)
    return v / (n / 10.0)


def ngrams(text, n=2):
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def clarity_of_item(it):
    """清晰度代理（真实题面，可复跑）：判据句（rationale）把哪一端的独特措辞讲清楚了。

    强制对比题的题干本来就共用情境句，所以「共用词多」不是含混的证据；真正能说明
    判据清不清楚的是：设计者写的理由里，有没有把某一端的**独特措辞**说出来。
    这个代理只用真实文本，算得出来、复跑得动；它是真人锚定审计的**抽样优先线索**，
    不是「题目好不好」的结论。
    """
    ta, tb = ngrams(it["a"]), ngrams(it["b"])
    ua, ub = ta - tb, tb - ta
    if not ua and not ub:
        return 0.5
    r = ngrams(it.get("rationale", ""))
    oa = len(ua & r) / len(ua) if ua else 0.0
    ob = len(ub & r) / len(ub) if ub else 0.0
    return round(max(0.0, min(1.0, max(oa, ob))), 3)


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def build_item_params(items, rng):
    params = []
    for it in items:
        a_disc = rng.uniform(0.70, 1.50)     # 区分度
        b_diff = rng.gauss(0.0, 0.80)        # 难度
        sd_a = social_desirability(it["a"])
        sd_b = social_desirability(it["b"])
        anchor_text = it["a"] if it["anchor"] == "a" else it["b"]
        other_text = it["b"] if it["anchor"] == "a" else it["a"]
        w = social_desirability(anchor_text) - social_desirability(other_text)
        params.append({
            "id": it["id"], "dim": it["dim"], "anchor": it["anchor"],
            "a_disc": round(a_disc, 4), "b_diff": round(b_diff, 4),
            "sd_a": round(sd_a, 3), "sd_b": round(sd_b, 3),
            "sd_pull": round(max(-1.2, min(1.2, w)), 3),
            "clarity": clarity_of_item(it),
        })
    return params


def gen_respondent(rid, group, profile, theta, params, rng, behavior, item_ids, flip_rate=0.0):
    """生成一份合成作答：responses 为 0/1（0 = 选 a 侧，1 = 选 b 侧），与成品里的口径一致。

    flip_rate 是「题目误差率」：作答后再按概率翻面。α 自检对照靠它把 α 压到不同水平，
    这样 α 计算器与 α≥0.70 的判定逻辑才有已知真值可验。
    """
    p = PROFILES[profile]
    fake = p["fake"] * math.exp(rng.gauss(0.0, 0.45))
    sd_sens = max(0.0, min(1.2, p["sd_sens"] * math.exp(rng.gauss(0.0, 0.20))))
    n = len(params)
    responses, times = [], []
    for ip in params:
        d = ip["dim"]
        if behavior == "straight_a":
            r = 0
        elif behavior == "straight_b":
            r = 1
        elif behavior == "random":
            r = rng.randint(0, 1)
        elif behavior == "perfect":
            r = 0 if ip["anchor"] == "a" else 1
        else:
            z = ip["a_disc"] * (theta[d] - ip["b_diff"]) + fake * ip["sd_pull"] * sd_sens
            r = 0 if ip["anchor"] == "a" else 1
            if rng.random() > sigmoid(z):
                r = 1 - r
        if flip_rate and rng.random() < flip_rate:
            r = 1 - r
        responses.append(r)
        if behavior == "fast":
            times.append(int(rng.uniform(1500, 2900)))
        elif behavior == "random":
            times.append(int(rng.uniform(1800, 3400)))
        else:
            times.append(int(math.exp(rng.gauss(math.log(11000), 0.45))))
    return {
        "id": rid, "group": group, "profile": profile,
        "theta": {d: round(theta[d], 4) for d in DIMS},
        "fake": round(fake, 4), "sd_sens": round(sd_sens, 4),
        "behavior": behavior,
        "responses": responses, "times_ms": times,
        "items": item_ids,
    }


def gen_dataset(seed, n, profile_mix, params, items, flip_rate=0.0, behaviors=None):
    """按比例生成一批样本；flip_rate 越大题目越不可靠（用于 α 自检对照）。"""
    rng = random.Random(seed)
    out = []
    profiles = list(profile_mix.keys())
    weights = [profile_mix[p] for p in profiles]
    total_w = float(sum(weights))
    behaviors = behaviors or {}
    beh_list = []
    for b, c in behaviors.items():
        beh_list += [b] * c
    for i in range(n):
        r = rng.random() * total_w
        acc = 0.0
        prof = profiles[-1]
        for p, w in zip(profiles, weights):
            acc += w
            if r <= acc:
                prof = p
                break
        theta = {d: PROFILES[prof]["theta"][d] + rng.gauss(0.0, 0.85) for d in DIMS}
        beh = beh_list[i] if i < len(beh_list) else "normal"
        out.append(gen_respondent("SIM-%04d" % (i + 1), "合成组", prof, theta, params, rng, beh,
                                   [it["id"] for it in items], flip_rate=flip_rate))
    return out


def gen_end_to_end(items, params, eq, m3, rng):
    """整卷端到端样本：第一项 + 第二项（16 自评 + 60 情境）+ 第三项 40 题。"""
    prof = "HR经理"
    theta = {d: PROFILES[prof]["theta"][d] + 0.15 for d in DIMS}
    r1 = gen_respondent("SIM-E2E", "整卷端到端", prof, theta, params, rng, "normal", [it["id"] for it in items])

    # 第二项：16 道自评（1–7），反向题取低分；60 道情境题按最优/次优/其他抽
    m2 = []
    for i, x in enumerate(eq["self_items"]):
        if x.get("reverse"):
            v = rng.choice([2, 3, 3, 4])
        else:
            v = rng.choice([5, 6, 6, 7])
        m2.append(v)
    for q in eq["sjt"]:
        opts = list("ABCD")
        ans = q.get("answer")
        sec = q.get("second")
        u = rng.random()
        if ans and u < 0.72:
            pick = ans
        elif sec and u < 0.92:
            pick = sec
        else:
            pick = rng.choice([o for o in opts if o != ans])
        m2.append(opts.index(pick))

    # 第三项：按难度给对错
    m3_ans = []
    for q in m3["questions"]:
        p = 0.82 - 0.05 * int(q.get("difficulty", 1))
        correct = q.get("answer")
        n_opt = len(q.get("options") or [])
        if correct is None or n_opt <= 1:
            m3_ans.append(0)
        elif rng.random() < p:
            m3_ans.append(correct)
        else:
            m3_ans.append(rng.choice([o for o in range(n_opt) if o != correct]))

    return {
        "id": "SIM-E2E", "group": "整卷端到端", "profile": prof,
        "theta": {d: round(theta[d], 4) for d in DIMS},
        "responses_m1": r1["responses"], "times_ms_m1": r1["times_ms"],
        "responses_m2": m2, "responses_m3": m3_ans,
        "name": "模拟候选人", "idLast4": "0000", "code": "SIM-20261024-E2E0001",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="额外生成 α 自检对照数据集")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    items = load_json("items/m1_items.json")["items"]
    eq = load_json("data/eq_bank_encoded.json")
    m3 = load_json("data/logic_m3.json")

    rng = random.Random(SEED)
    params = build_item_params(items, rng)
    item_ids = [it["id"] for it in items]

    # 异常样本均匀铺在整段序列里（两个组都有，避免把某一组压歪）：
    # 检测器不得看到这个标签，只能靠数据本身抓出来。
    anomaly_seq = []
    for b, c in ANOMALY_PLAN:
        anomaly_seq += [b] * c
    anomaly_at = {}
    if anomaly_seq:
        step = max(1, 120 // (len(anomaly_seq) + 1))
        for k, b in enumerate(anomaly_seq):
            anomaly_at[min(119, 4 + k * step)] = b

    respondents = []
    seq = 0
    for group, n, mix in GROUPS:
        pool = []
        for prof, c in mix.items():
            pool += [prof] * c
        pool = pool[:n] + pool[n:]  # 保持顺序，长度与 n 一致
        for prof in pool:
            theta = {d: PROFILES[prof]["theta"][d] + rng.gauss(0.0, 0.85) for d in DIMS}
            beh = anomaly_at.get(seq, "normal")
            seq += 1
            respondents.append(gen_respondent("SIM-%04d" % seq, group, prof, theta, params, rng, beh, item_ids))

    e2e = gen_end_to_end(items, params, eq, m3, random.Random(SEED + 7))

    payload = {
        "meta": {
            "seed": SEED,
            "note": "全部为合成数据，非真人样本；无任何信效度证据力",
            "groups": [{"name": g, "n": n, "mix": m} for g, n, m in GROUPS],
            "total": len(respondents),
            "items": len(items),
            "profiles": PROFILES,
        },
        "item_params": params,
        "respondents": respondents,
        "end_to_end": e2e,
    }

    if args.selftest:
        # 三份「已知信度水平」的数据集：题目误差率（翻面概率）越大 → α 越低。
        # 用途是检验 α 计算器与 α≥0.70 判定逻辑，而不是评价题目。
        st = []
        for tag, flip in (("low_reliability", 0.35), ("mid_reliability", 0.20), ("high_reliability", 0.05)):
            st.append({
                "tag": tag, "flip_rate": flip,
                "respondents": gen_dataset(SEED + 100 + int(flip * 100), 200,
                                          {"HR专员": 40, "HR经理": 40, "HR总监": 40},
                                          params, items, flip_rate=flip),
            })
        payload["selftest"] = st

    path = os.path.join(OUT, "samples.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("已生成 %s" % path)
    print("  样本 %d 份（%s）· 题 %d 道 · 异常注入 %d 份" % (
        len(respondents), " + ".join("%s %d" % (g, n) for g, n, _ in GROUPS), len(items),
        sum(c for _, c in ANOMALY_PLAN)))
    print("  整卷端到端样本 1 份（第一项 + 第二项 + 第三项）")


if __name__ == "__main__":
    main()
