#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可信度判缺验收门 —— 票 #51。

背景：规范 §11.4（测评设计规范_20261024.md:259-260）规定
「没有留存逐题作答的部分，可信度给『中』并写明『本次未留存逐题作答』，不许默认给『高』」。
但 report_narrative.credibility() 的 m1（人格特质）段在离线 9 字段路径
（m1_raw=None）下整段 if 被跳过，level 恒为「高」且无判缺 flag —— 违反 §11.4。
m2/m3 早有合规的判缺分支，本门把 m1 补齐后锁死这个行为。

验收（机器判定，不靠肉眼）：
  · 核心：离线 9 字段（m1_raw/m2_answers/m3_answers 全 None）下，m1/m2/m3
    三档**均 ≠ 高**，且每档 flags 含「未留存逐题作答」判缺标记。
  · 正向对照 A：有逐题、作答干净 ⇒ m1 仍可为「高」（证明降级只在缺数据时发生，不误伤有数据路径）。
  · 正向对照 B：有逐题、同侧连答 ≥25 ⇒ m1 判「低」（证明真实扣档路径未被改动）。

用法：python3 src/verify_credibility.py
退出码 0 = 合格；非 0 = 有项未通过。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from report_narrative import credibility  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("  [OK ] " if ok else "  [FAIL] ") + name + (("：" + detail) if detail else ""))


def main():
    # ---- 核心：离线 9 字段路径（三个逐题入参全 None）----
    cred = credibility({}, {}, {}, {})   # m1_raw/m2_answers/m3_answers 缺省 None
    for mod in ("m1", "m2", "m3"):
        lv = cred[mod]["level"]
        flags = " ".join(cred[mod]["flags"])
        check("9 字段下 %s 不给『高』（§11.4）" % mod, lv != "高", "实际 level=%s" % lv)
        check("9 字段下 %s 带判缺标记" % mod, "未留存逐题作答" in flags, "flags=%s" % (cred[mod]["flags"] or "[]"))
    check("9 字段下 m1 精确落『中』（无其他扣档）", cred["m1"]["level"] == "中",
          "实际 level=%s" % cred["m1"]["level"])

    # ---- 正向对照 A：有逐题、作答干净 ⇒ 仍可为「高」（不误伤有数据路径）----
    m1_raw_clean = [0, 1] * 48                     # 交替作答：无连答、某侧占比 50%
    data_clean = {"unanswered_m1": 0, "duration_ms": 212 * 30000}  # 无缺题、30 秒/题在区间内
    credA = credibility(data_clean, {}, {"consistency": []}, {},
                        m1_raw=m1_raw_clean, m2_answers=[1] * 20, m3_answers=[1] * 10)
    check("有逐题且干净 ⇒ m1 仍『高』（判缺不误伤）", credA["m1"]["level"] == "高",
          "实际 level=%s" % credA["m1"]["level"])

    # ---- 正向对照 B：有逐题、同侧连答 ≥25 ⇒ 判「低」（真实扣档路径未变）----
    m1_raw_run = [1] * 96                          # 全 1：连答 96 ≥ 25、占比 100% ⇒ 低
    credB = credibility({"unanswered_m1": 0}, {}, {}, {}, m1_raw=m1_raw_run)
    check("同侧连答 ≥25 ⇒ m1『低』（扣档路径未变）", credB["m1"]["level"] == "低",
          "实际 level=%s" % credB["m1"]["level"])

    bad = [n for n, ok in results if not ok]
    if bad:
        print("未通过：%s" % "、".join(bad))
        return 1
    print("可信度判缺验收全部通过（%d 项）" % len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
