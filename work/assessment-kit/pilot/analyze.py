#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模拟试测分析与判定 —— 票 #24（模拟版）。

本脚本做两件事，性质完全不同，必须分开看：

  A. **对真人试测有用的程序**：α / 分半信度怎么算、阈值怎么判、异常样本怎么抓、
     校准切点怎么算、锚定审计怎么记、真值能不能被计分还原。这部分现在就能验，
     真人样本到手后直接换数据重跑即可。

  B. **对合成数据的描述**：α 值、分布、极端题比例。真话是——**这些数字是生成
     模型的性质，不是题目的性质**。生成时噪声多大，α 就有多大；题目本身好不好，
     合成数据一个字都没说。所以本脚本对 α 一律标 `simulated` 前缀，报告里也不许
     把它当信效度证据。

用法：
    python3 pilot/analyze.py                     # 分析合成样本（默认）
    python3 pilot/analyze.py --real out/real.json --scored out/real_scored.json
                                                  # 真人数据：先 node pilot/run_pilot.mjs <真实样本> 计分
产物：pilot/out/analysis.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simulate import clarity_of_item, social_desirability  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "out")

DIMS = ["INT", "SNT", "TFS", "JPS"]
ORD = {"待提升": 1, "合格": 2, "良好": 3, "优秀": 4, "顶尖": 5}
ALPHA_MIN = 0.70      # 票 #24 验收阈值：每维 α ≥ 0.70
SPLIT_MIN = 0.70      # 票 #24 验收阈值：分半信度 ≥ 0.70
AUDIT_MIN = 0.80      # 票 #24 验收阈值：锚定审计命中率 ≥ 80%
DISAGREE_MAX = 0.15   # 规程：双人标注分歧率 > 15% → 整维重标
EXTREME_SAME = 0.90   # 社会赞许偏差观察：某题 90% 选同一端 → 该题判据可能太露骨
CORR_ALARM = 0.60     # 与第三项推理分的相关：|r| ≥ 0.60 → 查题目是否重叠
CALIB_MIN_N = 100     # 校准门槛：累计 ≥ 100 份有效作答才允许换参照分布切点


# ------------------------------------------------------------------ 基础统计
def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def var(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def pearson(a, b):
    n = len(a)
    if n < 3:
        return float("nan")
    ma, mb = mean(a), mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return num / (da * db) if da and db else float("nan")


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(a, b):
    return pearson(ranks(a), ranks(b))


def cronbach_alpha(matrix):
    """matrix：每人一行、每题一列的 0/1 得分矩阵。"""
    k = len(matrix[0])
    if k < 2 or len(matrix) < 3:
        return float("nan")
    item_vars = [var([row[j] for row in matrix]) for j in range(k)]
    total = [sum(row) for row in matrix]
    tvar = var(total)
    if tvar == 0:
        return float("nan")
    return (k / (k - 1.0)) * (1.0 - sum(item_vars) / tvar)


def split_half(matrix):
    """奇偶分半 + Spearman-Brown 校正。"""
    odd = [[row[j] for j in range(0, len(row), 2)] for row in matrix]
    even = [[row[j] for j in range(1, len(row), 2)] for row in matrix]
    so = [sum(r) for r in odd]
    se = [sum(r) for r in even]
    r = pearson(so, se)
    sb = (2 * r / (1 + r)) if r > -1 else float("nan")
    return {"odd_sum": so, "even_sum": se, "r": r, "spearman_brown": sb}


# ------------------------------------------- 区间（Feldt 型解析式 + 重抽样）
# 口径出处（仓内既有笔记，本轮不新查）：
#   research/样本量与信度推断边界_20261025.md §1.2（区间式，与 R 的 psych::alpha.ci 同式）
#     §1.4（唯一站得住的判定写法：整段区间在阈值同一侧）
#   research/信度结论写法_三选一_20261025.md §2.1（票 #29 裁定的 A 案报告模板）
# 仓内不依赖 scipy：F 分布分位数用正则化不完全贝塔 + 二分求解。

def _betacf(a, b, x, itmax=300, eps=3.0e-16, fpmin=1.0e-300):
    """连分式（Numerical Recipes 的 betacf）。"""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def betainc(a, b, x):
    """正则化不完全贝塔函数 I_x(a, b)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbeta + a * math.log(x) + b * math.log1p(-x)) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta + b * math.log1p(-x) + a * math.log(x)) * _betacf(b, a, 1.0 - x) / b


def f_cdf(x, d1, d2):
    """F 分布的累积分布。"""
    if x <= 0.0:
        return 0.0
    return betainc(d1 / 2.0, d2 / 2.0, d1 * x / (d1 * x + d2))


def f_quantile(p, d1, d2, iters=200):
    """F 分布分位数（对 CDF 二分求解）。"""
    lo = 0.0
    hi = 1.0
    while f_cdf(hi, d1, d2) < p and hi < 1.0e12:
        hi *= 2.0
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        if f_cdf(mid, d1, d2) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def alpha_ci_feldt(alpha_hat, n, k, conf=0.95):
    """α 的置信区间（Feldt 型解析式，等价于 R 的 psych::alpha.ci）。

    下界 = 1 − (1−α̂)·qF(1−(1−conf)/2, n−1, (n−1)(k−1))
    上界 = 1 − (1−α̂)·qF((1−conf)/2, n−1, (n−1)(k−1))
    """
    if not (alpha_hat == alpha_hat) or n < 3 or k < 2:
        return None
    d1 = float(n - 1)
    d2 = float((n - 1) * (k - 1))
    half = (1.0 - conf) / 2.0
    q_low = f_quantile(half, d1, d2)        # 小分位 → 区间上界
    q_high = f_quantile(1.0 - half, d1, d2)  # 大分位 → 区间下界
    return (1.0 - (1.0 - alpha_hat) * q_high, 1.0 - (1.0 - alpha_hat) * q_low)


def alpha_verdict(ci, threshold=ALPHA_MIN):
    """按「整段区间在阈值同一侧」下结论——票 #29 A 案唯一站得住的写法。

    三态：整段在阈值之上 / 整段在阈值之下 / 跨线（不确定，本轮不判定达标与否）。
    """
    if not ci:
        return {"verdict": "区间不可得（样本量或题数不足）", "class": "undetermined"}
    lo, hi = ci
    if lo > threshold:
        return {"verdict": "整段区间在 %.2f 之上（稳健达标）" % threshold, "class": "above"}
    if hi < threshold:
        return {"verdict": "整段区间在 %.2f 之下（内部一致性明显不足，需补题或合并维度）" % threshold,
                "class": "below"}
    return {"verdict": "区间跨线（结论只能是「不确定」，本轮不判定达标与否）", "class": "crossing"}


def percentile(values, p):
    """线性插值分位数（与 percentile_cutpoints 同一口径）。"""
    v = sorted(values)
    if not v:
        return float("nan")
    k = (p / 100.0) * (len(v) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    return v[int(k)] if f == c else v[f] + (v[c] - v[f]) * (k - f)


def split_half_ci(matrix, conf=0.95, reps=1000, seed=20261025):
    """分半信度的 95% 区间（重抽样；本项目没有可用的解析式）。

    口径出处：research/信度结论写法_三选一_20261025.md §2.1（分半区间须由重抽样给出）。
    """
    n = len(matrix)
    if n < 4:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(reps):
        m = [matrix[rng.randrange(n)] for _ in range(n)]
        v = split_half(m)["spearman_brown"]
        if v == v:
            vals.append(v)
    if len(vals) < 20:
        return None
    half = (1.0 - conf) / 2.0
    return (percentile(vals, half * 100.0), percentile(vals, (1.0 - half) * 100.0))


def alpha_gate(n, k, threshold=ALPHA_MIN, side="above"):
    """求「区间整段落在阈值同一侧」所需的 α̂ 门限（二分）。

    对应 research/样本量与信度推断边界_20261025.md §1.4 的那两张门限表。
    """
    def f(ah):
        ci = alpha_ci_feldt(ah, n, k)
        return (ci[0] - threshold) if side == "above" else (ci[1] - threshold)

    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        fm = f(mid)
        if side == "above":
            # f 随 α̂ 单调增：f(mid) ≥ 0 说明 mid 已在根之上
            if fm >= 0:
                hi = mid
            else:
                lo = mid
        else:
            # f 随 α̂ 单调增：f(mid) ≤ 0 说明还没到根，根更大
            if fm <= 0:
                lo = mid
            else:
                hi = mid
    return (lo + hi) / 2.0


# 自检基准：仓内笔记的公开表（口径出处见上）
CI_SELFTEST_TABLE = [
    (40, 0.72, 24, 0.578, 0.831), (60, 0.72, 24, 0.607, 0.813),
    (80, 0.72, 24, 0.623, 0.802), (100, 0.72, 24, 0.634, 0.794),
    (150, 0.72, 24, 0.651, 0.781), (200, 0.72, 24, 0.661, 0.773),
    (250, 0.72, 24, 0.667, 0.768), (300, 0.72, 24, 0.672, 0.764),
    (500, 0.72, 24, 0.683, 0.754), (1000, 0.72, 24, 0.694, 0.745),
    (60, 0.74, 24, 0.635, 0.826), (80, 0.74, 24, 0.650, 0.816),
    (300, 0.74, 24, 0.696, 0.781),
]
CI_GATE_TABLE = [
    (60, 0.7864, 0.5509), (80, 0.7770, 0.5767), (100, 0.7703, 0.5931),
    (200, 0.7524, 0.6297), (300, 0.7438, 0.6443), (500, 0.7348, 0.6581),
]


def run_ci_selftest(tol=0.001):
    """自检：区间实现能否复现仓内笔记的表（复现不了 ⇒ 实现不可用）。

    容差 0.001：笔记里的表是**三位小数**，舍入本身带来 ±0.0005（笔记 §1.4 也这么记）。
    """
    worst = 0.0
    for n, ah, k, elo, ehi in CI_SELFTEST_TABLE:
        lo, hi = alpha_ci_feldt(ah, n, k)
        d = max(abs(lo - elo), abs(hi - ehi))
        worst = max(worst, d)
        print("区间 n=%-5d a_hat=%.2f k=%d  实算[%.4f, %.4f]  笔记[%.3f, %.3f]  偏差 %.5f  %s" % (
            n, ah, k, lo, hi, elo, ehi, d, "OK" if d <= tol else "不一致"))
    for n, gabove, gbelow in CI_GATE_TABLE:
        ga = alpha_gate(n, 24, side="above")
        gb = alpha_gate(n, 24, side="below")
        da, db = abs(ga - gabove), abs(gb - gbelow)
        worst = max(worst, da, db)
        print("门限 n=%-5d 之上 实算 %.4f / 笔记 %.4f（差 %.4f）  之下 实算 %.4f / 笔记 %.4f（差 %.4f）" % (
            n, ga, gabove, da, gb, gbelow, db))
    print("最大绝对偏差 %.5f（容差 %.4f）→ %s" % (worst, tol, "通过" if worst <= tol else "不通过"))
    return worst <= tol


def percentile_cutpoints(values):
    """按参照分布切点：P90 顶尖 / P70 优秀 / P45 良好 / P25 合格。"""
    v = sorted(values)
    n = len(v)

    def pct(p):
        if n == 0:
            return 0
        k = (p / 100.0) * (n - 1)
        f = math.floor(k)
        c = math.ceil(k)
        return v[int(k)] if f == c else v[f] + (v[c] - v[f]) * (k - f)

    return {"顶尖": pct(90), "优秀": pct(70), "良好": pct(45), "合格": pct(25)}


def band_by_cutpoints(score, cuts):
    if score >= cuts["顶尖"]:
        return "顶尖"
    if score >= cuts["优秀"]:
        return "优秀"
    if score >= cuts["良好"]:
        return "良好"
    if score >= cuts["合格"]:
        return "合格"
    return "待提升"


def band_by_anchor(score, bands):
    for k in ("顶尖", "优秀", "良好", "合格"):
        lo, hi = bands[k]
        if lo <= score <= hi:
            return k
    return "待提升"


# ------------------------------------------------------------ 独立复算计分
def score_m1_python(items, responses):
    """独立于 report.js 复算一遍，用于交叉验算计分口径。"""
    bands = BANDS
    dims = []
    for d in DIMS:
        sc = 0
        for it, resp in zip(items, responses):
            if it["dim"] != d:
                continue
            if (it["anchor"] == "a" and resp == 0) or (it["anchor"] == "b" and resp == 1):
                sc += 1
        dims.append({"key": d, "score": sc, "grade": band_by_anchor(sc, bands)})
    grade = sorted(dims, key=lambda x: ORD[x["grade"]])[0]["grade"]
    return dims, grade


# ------------------------------------------------------------ 异常样本检测
def detect_anomalies(r, nominal_min=12.0):
    """盲检：不看 behavior 标签，只看作答与时长。

    阈值都是**临时值**：真人的逐题作答时间还没采集过，这里先用合成数据把规则
    跑通并给出召回/精确率；真人试测拿到真实时长分布后必须重新标定。
    """
    resp = r["responses"]
    times = r.get("times_ms") or []
    flags = []
    n = len(resp)
    # 逐题耗时可能没有（自助链接模式服务端拿不到逐题时间）；
    # 没有就不做这两条**时长类**粗筛，而不是当成 0 秒去报警。
    if times and len(times) == n:
        total_min = sum(times) / 60000.0
        per_item_s = total_min * 60.0 / n
        if per_item_s < 3.0:
            flags.append("平均每题 < 3 秒")
        if total_min < nominal_min * 0.40:
            flags.append("总时长不足名义时长 40%")
    same = max(sum(1 for x in resp if x == 0), sum(1 for x in resp if x == 1)) / n
    if same > 0.90:
        flags.append("同侧作答 > 90%")
    # 与锚定端完全一致（全选有效端）= 装分到极致，需人工看
    anchors = [it["anchor"] for it in ITEMS]
    if all((a == "a" and x == 0) or (a == "b" and x == 1) for a, x in zip(anchors, resp)):
        flags.append("96 题全选锚定端")
    # 随机性：相邻题同侧比例显著高于 0.5 → 直线作答
    adj = sum(1 for i in range(n - 1) if resp[i] == resp[i + 1]) / (n - 1)
    if adj > 0.80:
        flags.append("相邻同侧 > 80%")
    return flags


# ------------------------------------------------------- 锚定审计（程序演练）
def simulate_anchor_audit(dim_items, params, seed=20261024, n_annotators=6):
    """模拟标注员在「有效端换到另一侧」后是否还能选出同一个行为。

    两种错误来源，都要能被抓到：
      · 措辞含混（清晰度低）→ 原版就选错，换位后也选错 → 命中率低
      · 位置 / 社会赞许偏好 → 原版选对，换位后跟着位置走 → 命中率低
    真人的锚定审计要由真人标注员执行；这里只验「审计程序本身能不能分辨」。
    """
    rng = random.Random(seed)
    by_id = {p["id"]: p for p in params}
    out = {}
    for d in DIMS:
        its = [it for it in dim_items if it["dim"] == d]
        picked = rng.sample(its, 6)
        hits, trials = 0, 0
        for it in picked:
            p = by_id[it["id"]]
            eff_text = it["a"] if it["anchor"] == "a" else it["b"]
            oth_text = it["b"] if it["anchor"] == "a" else it["a"]
            c = p["clarity"]
            sd_eff = p["sd_a"] if it["anchor"] == "a" else p["sd_b"]
            sd_oth = p["sd_b"] if it["anchor"] == "a" else p["sd_a"]
            for _ in range(n_annotators):
                # 标注员特质：位置偏好 π、听词偏好 β、理解力 u
                pi = rng.gauss(0.0, 0.55)
                beta = rng.gauss(0.0, 0.55)
                u = rng.gauss(0.0, 0.35)
                # 原版：a 在前
                pa = c * (1 if it["anchor"] == "a" else -1) + beta * sd_a_of(p, "a") + pi * 1 + u
                pb = c * (1 if it["anchor"] == "b" else -1) + beta * sd_a_of(p, "b") + pi * -1 + u
                # 换位版：a 移到后面
                pa2 = c * (1 if it["anchor"] == "a" else -1) + beta * sd_a_of(p, "a") + pi * -1 + u
                pb2 = c * (1 if it["anchor"] == "b" else -1) + beta * sd_a_of(p, "b") + pi * 1 + u
                pick_orig = "a" if pa >= pb else "b"
                pick_swap = "a" if pa2 >= pb2 else "b"
                # 命中 = 换位后仍选中「声明的有效端那一条陈述」
                if pick_swap == it["anchor"]:
                    hits += 1
                trials += 1
        out[d] = {"n_items": 6, "trials": trials, "hit_rate": round(hits / trials, 4)}
    return out


def sd_a_of(p, side):
    return p["sd_a"] if side == "a" else p["sd_b"]


# --------------------------------------------------------------------- 主流程
def main():
    global ITEMS, BANDS
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", metavar="PATH", help="真人作答文件（格式见真人试测作业包 §6）")
    ap.add_argument("--scored", metavar="PATH", help="计分结果文件，默认 pilot/out/scored.json")
    ap.add_argument("--exclude", metavar="PATH", help="要剔除的样本 id 清单（人工确认后的异常样本）")
    ap.add_argument("--selftest-ci", action="store_true",
                    help="自检：区间实现能否复现仓内笔记 §1.2 / §1.4 的表（不读数据、不写文件）")
    args = ap.parse_args()
    if args.selftest_ci:
        sys.exit(0 if run_ci_selftest() else 1)
    real_mode = bool(args.real)

    with open(os.path.join(ROOT, "items", "m1_items.json"), encoding="utf-8") as f:
        m1 = json.load(f)
    ITEMS = m1["items"]
    BANDS = m1["meta"]["bands"]

    samples_path = args.real if real_mode else os.path.join(OUT, "samples.json")
    samples = json.load(open(samples_path, encoding="utf-8"))
    scored_path = args.scored if args.scored else os.path.join(OUT, "scored.json")
    scored = json.load(open(scored_path, encoding="utf-8"))["scored"]
    # 真人数据没有 item_params（那是合成模型的参数），清晰度代理改从题库现算
    params = samples.get("item_params") or [
        {"id": it["id"], "clarity": clarity_of_item(it), "sd_a": 0.0, "sd_b": 0.0}
        for it in ITEMS
    ]

    resp_by_id = {r["id"]: r for r in samples["respondents"]}
    res = {"note": ("真人作答数据" if real_mode else "全部数字来自合成样本；α/分布为生成模型性质，不是题目性质"),
           "samples_file": samples_path,
           "n_respondents": len(samples["respondents"])}

    # ---- A. 交叉验算：Python 独立复算 vs 成品真实计分 ----
    mismatch = 0
    checked = 0
    for s in scored:
        r = resp_by_id[s["id"]]
        dims, grade = score_m1_python(ITEMS, r["responses"])
        for mine, theirs in zip(dims, s["m1"]["dims"]):
            checked += 1
            if mine["score"] != theirs["score"] or mine["grade"] != theirs["grade"]:
                mismatch += 1
        if grade != s["m1"]["grade"]:
            mismatch += 1
    res["cross_check"] = {"compared": checked, "mismatch": mismatch,
                          "verdict": "两套独立实现逐格一致" if mismatch == 0 else "计分口径有分歧，必须先修"}

    # ---- B. 异常样本盲检（合成数据有真值标签可对照；真人数据没有，只报检出） ----
    tp = fp = fn = 0
    det_rows = []
    for s in scored:
        r = resp_by_id[s["id"]]
        flags = detect_anomalies(r)
        has_truth = bool(r.get("behavior"))
        truth = has_truth and r["behavior"] != "normal"
        pred = len(flags) > 0
        if truth and pred:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif truth and not pred:
            fn += 1
        if pred or truth:
            det_rows.append({"id": s["id"], "behavior": r.get("behavior"), "flags": flags,
                             "detected": pred})
    res["anomaly_detection"] = {"detected": tp + fp, "true_anomaly": tp + fn,
                                "hit": tp, "false_alarm": fp, "missed": fn,
                                "recall": round(tp / max(1, tp + fn), 3) if (tp + fn) else None,
                                "precision": round(tp / max(1, tp + fp), 3) if (tp + fp) else None,
                                "note": ("合成数据：召回/精确率是自检指标" if not real_mode
                                         else "真人数据：无真值标签，只有检出清单，需施测人人工复核"),
                                "rows": det_rows}

    # ---- C. 每维信度 ----
    # 合成数据下这些数字是生成模型的性质；真人数据下才是题目的性质。
    exclude = set()
    if args.exclude:
        raw = open(args.exclude, encoding="utf-8").read().strip()
        try:
            lst = json.loads(raw)
            exclude = set(lst) if isinstance(lst, list) else set()
        except Exception:
            exclude = set(x.strip() for x in raw.splitlines() if x.strip())
    rel = {}
    for d in DIMS:
        cols = [i for i, it in enumerate(ITEMS) if it["dim"] == d]
        mat = []
        for r in samples["respondents"]:
            if r["id"] in exclude:
                continue                      # 人工确认剔除的样本
            if r.get("behavior") and r["behavior"] != "normal":
                continue      # 已知异常样本不进信度统计（真人数据无此标签）
            row = []
            for j in cols:
                it = ITEMS[j]
                x = r["responses"][j]
                row.append(1 if ((it["anchor"] == "a" and x == 0) or (it["anchor"] == "b" and x == 1)) else 0)
            mat.append(row)
        a = cronbach_alpha(mat)
        sh = split_half(mat)
        ci = alpha_ci_feldt(a, len(mat), len(cols))
        sb_ci = split_half_ci(mat)
        vd = alpha_verdict(ci)
        rel[d] = {
            "n": len(mat), "k": len(cols),
            "alpha": round(a, 4),
            "alpha_ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
            "alpha_ci_halfwidth": round((ci[1] - ci[0]) / 2.0, 4) if ci else None,
            "alpha_verdict": vd["verdict"], "alpha_verdict_class": vd["class"],
            "alpha_pass": bool(a >= ALPHA_MIN),
            "alpha_pass_meaning": "点比较留痕，不是判定；判定看 alpha_verdict（票 #29 A 案）",
            "split_half_r": round(sh["r"], 4),
            "split_half_sb": round(sh["spearman_brown"], 4),
            "split_half_ci95": [round(sb_ci[0], 4), round(sb_ci[1], 4)] if sb_ci else None,
            "split_pass": bool(sh["spearman_brown"] >= SPLIT_MIN),
            "data_kind": "real" if real_mode else "simulated",
        }
    res["reliability"] = rel
    res["excluded_ids"] = sorted(exclude)
    res["reliability_report_rule"] = (
        "第一轮按票 #29 裁定的 A 案：报 α̂ 与 95%% 区间，不判达标与否；"
        "只有区间整段落在 %.2f 同一侧才写结论（alpha_verdict）。" % ALPHA_MIN)

    # ---- C2. 第 13 条的两个数：完成整卷比例 / 省略作答比例 ----
    # 口径出处：票 #26 第 13 条 + research/限时口径与计时效应_20261024.md（Standards 4.14）。
    # D3（到点只提示、不自动交卷）之后，「被自动交卷截断的份数」恒为 0，
    # 这两个数变成「有多少人自己结束了」与「有多少人留了空题」，不再被截断污染。
    n_all = len(samples["respondents"])
    comp = {"n_total": n_all, "complete": 0, "incomplete": 0, "unanswered_total": 0,
            "limit_hint_rows": [], "per_respondent": []}
    for r in samples["respondents"]:
        resp = r.get("responses") or []
        ans = sum(1 for x in resp if isinstance(x, (int, float)) and not isinstance(x, bool) and x in (0, 1))
        miss = len(resp) - ans
        comp["unanswered_total"] += miss
        if ans == len(resp) and len(resp) > 0:
            comp["complete"] += 1
        else:
            comp["incomplete"] += 1
        row = {"id": r.get("id"), "answered": ans, "total": len(resp), "unanswered": miss}
        hint = r.get("limit_hint")
        if hint:
            row["limit_hint"] = hint
            comp["limit_hint_rows"].append(row)
        comp["per_respondent"].append(row)
    comp["complete_ratio"] = round(comp["complete"] / n_all, 4) if n_all else None
    comp["incomplete_ratio"] = round(comp["incomplete"] / n_all, 4) if n_all else None
    comp["note"] = ("第 13 条：完成整卷比例 = 整卷答完的份数占比；省略作答比例 = 有未答题的份数占比。"
                    "D3（到点只提示、不自动交卷）后不再有「被自动截断」的份数。")
    res["completion"] = comp

    # ---- D. α 自检对照：已知信度水平的数据集，α 计算器必须排对序 ----
    st_rows = []
    for ds in samples.get("selftest", []):
        mat = []
        for r in ds["respondents"]:
            row = []
            for j, it in enumerate(ITEMS):
                x = r["responses"][j]
                row.append(1 if ((it["anchor"] == "a" and x == 0) or (it["anchor"] == "b" and x == 1)) else 0)
            mat.append(row)
        by_dim = {}
        for d in DIMS:
            cols = [i for i, it in enumerate(ITEMS) if it["dim"] == d]
            sub = [[row[j] for j in cols] for row in mat]
            by_dim[d] = round(cronbach_alpha(sub), 4)
        avg = round(mean(list(by_dim.values())), 4)
        st_rows.append({"tag": ds["tag"], "flip_rate": ds.get("flip_rate"), "alpha_by_dim": by_dim,
                        "alpha_avg": avg, "judge_pass": bool(avg >= ALPHA_MIN)})
    order_ok = None
    if len(st_rows) == 3:
        by_tag = {r["tag"]: r["alpha_avg"] for r in st_rows}
        order_ok = (by_tag["high_reliability"] > by_tag["mid_reliability"] > by_tag["low_reliability"])
    res["alpha_selftest"] = {
        "rows": st_rows, "ordering_ok": order_ok,
        "verdict": ("α 计算器与 α≥0.70 判定在已知信度对照上表现正确" if order_ok else
                    ("α 计算器或判定逻辑有问题" if order_ok is not None else
                     "本次数据无自检对照（自检只在合成数据上做过）"))}

    # ---- E. 分布与极端题（社会赞许偏差观察） ----
    dist = {}
    for d in DIMS:
        scores = [s["m1"]["dims"][DIMS.index(d)]["score"] for s in scored]
        bands = {}
        for s in scored:
            g = s["m1"]["dims"][DIMS.index(d)]["grade"]
            bands[g] = bands.get(g, 0) + 1
        dist[d] = {"mean": round(mean(scores), 2), "sd": round(math.sqrt(var(scores)), 2),
                   "min": min(scores), "max": max(scores),
                   "band_counts": bands, "n": len(scores)}
    res["distribution_simulated"] = dist

    extreme = []
    for j, it in enumerate(ITEMS):
        p_same = sum(1 for r in samples["respondents"]
                      if (r["responses"][j] == 0) == (it["anchor"] == "a")) / len(samples["respondents"])
        pick_a = sum(1 for r in samples["respondents"] if r["responses"][j] == 0) / len(samples["respondents"])
        if max(pick_a, 1 - pick_a) >= EXTREME_SAME:
            extreme.append({"id": it["id"], "dim": it["dim"],
                            "picked_anchor_rate": round(p_same, 3),
                            "pick_a_rate": round(pick_a, 3),
                            "text_a": it["a"], "text_b": it["b"]})
    res["extreme_items_simulated"] = {"threshold": EXTREME_SAME, "count": len(extreme),
                                      "items": extreme}

    # ---- F. 锚定审计程序演练 + 真实题目的清晰度代理排序 ----
    audit = simulate_anchor_audit(ITEMS, params)
    for d in DIMS:
        audit[d]["pass_simulated"] = bool(audit[d]["hit_rate"] >= AUDIT_MIN)
    res["anchor_audit_simulated"] = audit
    # 清晰度代理（真实题面，可复跑）→ 真人审计的优先抽样清单
    by_id = {p["id"]: p for p in params}
    audit_priority = {}
    for d in DIMS:
        its = [it for it in ITEMS if it["dim"] == d]
        ranked = sorted(its, key=lambda it: by_id[it["id"]]["clarity"])
        audit_priority[d] = [{"id": it["id"], "clarity_proxy": by_id[it["id"]]["clarity"],
                               "len_a": len(it["a"]), "len_b": len(it["b"]),
                               "a": it["a"], "b": it["b"]} for it in ranked[:6]]
    res["audit_priority_real"] = audit_priority

    # ---- G. 真值回收（只有合成数据有注入真值；真人数据无此项） ----
    has_theta = bool(resp_by_id) and all("theta" in r for r in resp_by_id.values())
    rec = {}
    if has_theta:
        for d in DIMS:
            th = [resp_by_id[s["id"]]["theta"][d] for s in scored]
            sc = [s["m1"]["dims"][DIMS.index(d)]["score"] for s in scored]
            rec[d] = {"pearson": round(pearson(th, sc), 4), "spearman": round(spearman(th, sc), 4)}
        tot_theta = [sum(resp_by_id[s["id"]]["theta"].values()) for s in scored]
        tot_score = [sum(dd["score"] for dd in s["m1"]["dims"]) for s in scored]
        rec["总分"] = {"pearson": round(pearson(tot_theta, tot_score), 4),
                       "spearman": round(spearman(tot_theta, tot_score), 4)}
    res["truth_recovery"] = rec if rec else {"note": "真人数据没有注入真值，本项不适用"}

    # ---- H. 校准演示（演示用，不写裁定表） ----
    calib = {}
    for d in DIMS:
        scores = [s["m1"]["dims"][DIMS.index(d)]["score"] for s in scored]
        cuts = percentile_cutpoints(scores)
        before = {}
        after = {}
        for s in scored:
            sc = s["m1"]["dims"][DIMS.index(d)]["score"]
            g1 = band_by_anchor(sc, BANDS)
            g2 = band_by_cutpoints(sc, cuts)
            before[g1] = before.get(g1, 0) + 1
            after[g2] = after.get(g2, 0) + 1
        calib[d] = {"cuts_demo": {k: round(v, 2) for k, v in cuts.items()},
                    "absolute_anchor_counts": before, "percentile_counts_demo": after,
                    "n": len(scores), "meets_calib_n": len(scores) >= CALIB_MIN_N}
    res["calibration_demo"] = calib

    # ---- I. 与第三项推理分的相关性：检查器必须「弱相关不报警、强相关报警」 ----
    rng = random.Random(7)
    m1_tot = [sum(dd["score"] for dd in s["m1"]["dims"]) for s in scored]
    mu, sd = mean(m1_tot), math.sqrt(var(m1_tot))
    corr_rows = []
    if sd == 0 or len(m1_tot) < 2:
        # 样本不足（第一项总分无变异，sd=0）：模拟检验没有意义，**跳过而不是崩**
        # （2026-10-25：n=1 的第一份真实作答会在这里除零）
        res["correlation_check"] = {"threshold": CORR_ALARM, "rows": [],
                                    "skipped": "样本不足（第一项总分无变异），模拟检验跳过"}
        res["correlation_check"]["rows"] = []
        res["correlation_check"]["_skip"] = True
    else:
      for tag, rho in (("预期弱相关", 0.15), ("题目重叠嫌疑", 0.80)):
        z = [rng.gauss(0, 1) for _ in m1_tot]
        m3 = [rho * (x - mu) / sd + math.sqrt(max(0.0, 1 - rho * rho)) * zi for x, zi in zip(m1_tot, z)]
        r = pearson(m1_tot, m3)
        corr_rows.append({"case": tag, "rho_designed": rho, "r_observed": round(r, 4),
                          "alarm": bool(abs(r) >= CORR_ALARM)})
      res["correlation_check"] = {"threshold": CORR_ALARM, "rows": corr_rows}

    # ---- J. 分组对比（合成画像混合的结果，不是人群结论） ----
    grp = {}
    for g in ("内部候选人", "在职员工"):
        ss = [s for s in scored if s["group"] == g]
        if not ss:
            continue
        grp[g] = {"n": len(ss),
                  "dim_mean": {d: round(mean([s["m1"]["dims"][DIMS.index(d)]["score"] for s in ss]), 2) for d in DIMS},
                  "grade_counts": {}}
        for s in ss:
            grp[g]["grade_counts"][s["m1"]["grade"]] = grp[g]["grade_counts"].get(s["m1"]["grade"], 0) + 1
    res["group_compare_simulated"] = grp

    # ---- K. 真实题面的机械观察（不依赖真人，可复跑；只是线索，不是改题依据） ----
    obs = {"len_diff": [], "absolute_words": [], "both_positive": []}
    ABS_WORDS = ["总是", "从来", "永远", "必须", "所有", "任何", "绝对", "完全", "根本", "一律"]
    for it in ITEMS:
        obs["len_diff"].append(abs(len(it["a"]) - len(it["b"])))
        hit = [w for w in ABS_WORDS if w in it["a"] or w in it["b"]]
        if hit:
            obs["absolute_words"].append({"id": it["id"], "words": hit})
        sa = social_like(it["a"])
        sb = social_like(it["b"])
        if sa > 0 and sb > 0:
            obs["both_positive"].append({"id": it["id"], "a": it["a"], "b": it["b"]})
    res["item_text_observations_real"] = {
        "len_diff_max": max(obs["len_diff"]),
        "len_diff_mean": round(mean(obs["len_diff"]), 2),
        "absolute_words": obs["absolute_words"],
        "both_sides_positive_wording": obs["both_positive"],
        "note": "机械文本特征，只作真人标注与审计的优先线索，不构成改题依据",
    }

    with open(os.path.join(OUT, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    # ------------------------------------------------------------ 打印摘要
    print("== %s（样本 %d 份 · %s）==" % (
        "真人试测分析" if real_mode else "模拟试测分析（合成数据）",
        len(samples["respondents"]), samples_path))
    print("交叉验算：%s（比对 %d 格，不一致 %d）" % (
        res["cross_check"]["verdict"], res["cross_check"]["compared"], res["cross_check"]["mismatch"]))
    ad = res["anomaly_detection"]
    if ad["recall"] is not None:
        print("异常盲检：命中 %d / 真实异常 %d / 误报 %d / 漏报 %d（召回 %.2f，精确 %.2f）" % (
            ad["hit"], ad["true_anomaly"], ad["false_alarm"], ad["missed"], ad["recall"], ad["precision"]))
    else:
        print("异常盲检：检出 %d 份，需施测人人工复核（%s）" % (ad["detected"], ad["note"]))
    for d in DIMS:
        r = res["reliability"][d]
        tag = "" if real_mode else "(模拟)"
        if real_mode:
            ci = r["alpha_ci95"]
            sci = r["split_half_ci95"]
            print("  %s α%s=%.3f 95%%区间[%s]  分半SB%s=%.3f 95%%区间[%s]  → %s" % (
                d, tag, r["alpha"],
                ("%.3f, %.3f" % (ci[0], ci[1])) if ci else "不可得",
                tag, r["split_half_sb"],
                ("%.3f, %.3f" % (sci[0], sci[1])) if sci else "不可得",
                r["alpha_verdict"]))
        else:
            print("  %s α%s=%.3f  分半SB%s=%.3f  α点比较=%s 分半点比较=%s（合成数据，非信效度证据）" % (
                d, tag, r["alpha"], tag, r["split_half_sb"],
                "过" if r["alpha_pass"] else "不过",
                "过" if r["split_pass"] else "不过"))
    cp = res["completion"]
    print("  第13条：完成整卷 %d/%d（%s）  省略作答 %d/%d（%s）  未答题合计 %d  到点提示后仍作答 %d 份" % (
        cp["complete"], cp["n_total"],
        ("%.1f%%" % (cp["complete_ratio"] * 100)) if cp["complete_ratio"] is not None else "—",
        cp["incomplete"], cp["n_total"],
        ("%.1f%%" % (cp["incomplete_ratio"] * 100)) if cp["incomplete_ratio"] is not None else "—",
        cp["unanswered_total"], len(cp["limit_hint_rows"])))
    st_rows = res["alpha_selftest"]["rows"]
    print("  α 自检对照：%s%s" % (
        res["alpha_selftest"]["verdict"],
        ("（%s）" % " / ".join("%s α=%.3f" % (r["tag"], r["alpha_avg"]) for r in st_rows))
        if st_rows else ""))
    for d in DIMS:
        dd = res["distribution_simulated"][d]
        print("  %s 分布：均值 %.2f 标准差 %.2f 范围 %d–%d 绝对锚点档位 %s" % (
            d, dd["mean"], dd["sd"], dd["min"], dd["max"], dd["band_counts"]))
    print("  极端题（≥90%% 同端）：%d 道" % res["extreme_items_simulated"]["count"])
    for d in DIMS:
        a = res["anchor_audit_simulated"][d]
        print("  %s 锚定审计演练命中率 %.2f（阈值 %.2f → %s）" % (
            d, a["hit_rate"], AUDIT_MIN, "过" if a["pass_simulated"] else "不过"))
    if has_theta:
        for d in DIMS:
            t = res["truth_recovery"][d]
            print("  %s 真值回收：r=%.3f ρ=%.3f" % (d, t["pearson"], t["spearman"]))
    for row in res["correlation_check"]["rows"]:
        print("  相关性检查 %s：设计 ρ=%.2f → 实测 r=%.3f，%s" % (
            row["case"], row["rho_designed"], row["r_observed"], "报警" if row["alarm"] else "不报警"))
    for d in DIMS:
        c = res["calibration_demo"][d]
        print("  %s 校准演示：绝对锚点 %s → 百分位 %s（n=%d，门槛 %d）" % (
            d, c["absolute_anchor_counts"], c["percentile_counts_demo"], c["n"], CALIB_MIN_N))
    print("已写出 pilot/out/analysis.json")


def social_like(text):
    from simulate import social_desirability
    return social_desirability(text)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, HERE)
    main()
