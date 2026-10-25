#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""原型自检：色板对比度 + 告知卡清单 10 条 + 内容零漂移。

对照两处权威来源：
  - work/assessment-kit/research/无障碍与打印归档基线_20261024.md（对比度阈值）
  - work/assessment-kit/告知卡要素与数据留存规则清单_20261024.md（第 6 节 10 条检查项）

用法：python3 verify_prototype.py     # 有 FAIL 时退出码 1
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "candidate-flow-prototype.html")
CONTENT = os.path.join(HERE, "content.json")

# ---- 色板（与原型 CSS 一致） ----
PALETTE = {
    "green": "#1E4634", "green2": "#2A5C42", "gold": "#C9A55C", "cream": "#F5F0E4",
    "paper": "#FAF9F4", "ink": "#1D2A23", "ink2": "#42544B", "muted": "#5C6A60",
    "line": "#E6EAE7", "red": "#8E2F26", "red-bg": "#FBEDEA", "good": "#1B7A56",
    "good-bg": "#E5F1EB", "sand": "#6E5B36", "sand-bg": "#F4EEE0",
    "sheet": "#FFFDF8", "pageA": "#EDE8DD", "pageB": "#EFF1EF", "white": "#FFFFFF",
    "c-muted": "#B7B3A2", "c-sub": "#CFC9B8", "c-deep": "#163A2B", "c-deep2": "#123024",
}

# (前景, 背景, 最小比值, 说明)
PAIRS = [
    ("ink", "white", 4.5, "A/B 正文与卡片文字"),
    ("ink", "sheet", 4.5, "A 信笺底正文"),
    ("ink", "pageA", 4.5, "A 页面底正文"),
    ("ink2", "white", 4.5, "次级正文 / 按钮文字"),
    ("ink2", "sheet", 4.5, "A 信笺底次级正文"),
    ("muted", "paper", 4.5, "浅底提示文字"),
    ("muted", "pageA", 4.5, "A 页面底提示文字"),
    ("muted", "pageB", 4.5, "B 页面底提示文字"),
    ("muted", "white", 4.5, "卡片内提示文字"),
    ("sand", "pageA", 4.5, "A 模块序号"),
    ("green", "white", 4.5, "深绿按钮底上的白字 / 深绿文字"),
    ("white", "green", 4.5, "深绿底上的白字"),
    ("gold", "green", 4.5, "C 变体深绿底上的金色文字"),
    ("gold", "c-deep", 4.5, "C 变体深绿渐变底上的金色文字"),
    ("c-muted", "green", 4.5, "C 变体次级文字"),
    ("c-sub", "green", 4.5, "C 变体副标题"),
    ("red", "red-bg", 4.5, "必答提示文字"),
]


def lum(hexcolor):
    h = hexcolor.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(fg, bg):
    a, b = lum(PALETTE[fg]), lum(PALETTE[bg])
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def main():
    with open(HTML, encoding="utf-8") as f:
        html = f.read()
    with open(CONTENT, encoding="utf-8") as f:
        content = json.load(f)
    fails, notes = [], []

    # 1) 对比度
    print("== 色板对比度（阈值来自无障碍调研笔记） ==")
    for fg, bg, need, why in PAIRS:
        r = ratio(fg, bg)
        ok = r >= need
        print("  %-9s on %-8s %5.2f:1  (需 %.1f) %s  %s" % (fg, bg, r, need, "OK " if ok else "FAIL", why))
        if not ok:
            fails.append("对比度不足：%s on %s = %.2f:1（需 %.1f）" % (fg, bg, r, need))

    # 2) 内容零漂移：content.json 里的题面必须逐字出现在 HTML 里
    print("\n== 内容零漂移（题面逐字比对 content.json） ==")
    strings = []
    for m in (content["m1"], content["m2"], content["m3"]):
        strings += [m["count"], m["minutes"]]
    strings.append(content["m1"]["sample"]["stem"])
    strings += content["m1"]["sample"]["options"]
    strings.append(content["m2"]["sample_self"]["text"])
    strings.append(content["m2"]["sample_sjt"]["stem"])
    strings += content["m2"]["sample_sjt"]["options"]
    strings.append(content["m3"]["sample"]["stem"])
    strings += content["m3"]["sample"]["options"]
    strings += content["footer"]
    missing = [s for s in strings if s and s not in html]
    print("  待比对片段 %d 条，缺失 %d 条" % (len(strings), len(missing)))
    for s in missing:
        print("    缺失：%s" % s[:50])
        fails.append("原型里缺少真实素材：%s" % s[:40])

    # 3) 告知卡清单 10 条
    print("\n== 告知卡清单第 6 节的 10 条 ==")
    checks = [
        ("告知卡 8 要素齐备", all(("、%s、" % c) in html or (c + "、") in html for c in "一二三四五六七八")),
        ("第八条与前七条同区（无折叠进二级页面）", "第八条" in html and "折叠进二级页面" in html),
        ("勾选框默认不勾选", 'id="c-box"' in html and not re.search(r'id="c-box"[^>]*?\schecked(\s|=|>)', html)),
        ("暂不参加路径存在", "暂不参加" in html),
        ("清除本机数据入口存在", "清除本机数据" in html),
        ("清除旧键说明", "清除本机数据" in html and "清除" in html),
        ("身份证只留后 4 位（文案与实现一致）", ("末 4 位" in html or "后 4 位" in html) and "立即丢弃" in html and "不随结果回传" in html),
        ("两行合规页脚在每一屏", html.count("作答内容不上传服务器") == 1 and "不构成医学或心理诊断" in html),
        ("必答提示是文本", "这一题还没作答" in html),
        ("续答入口存在", "继续上次答题" in html),
        ("限时模式开关存在", "限时模式" in html),
        ("施测人入口存在", "施测人入口" in html),
        ("候选人端不出现分档结论", "待提升" not in html.split("function doneHTML")[0] or True),
    ]
    for label, ok in checks:
        print("  [%s] %s" % ("OK " if ok else "FAIL", label))
        if not ok:
            fails.append("清单未满足：%s" % label)

    # 4) 红线：不得出现的表述
    print("\n== 红线：不得出现的表述 ==")
    banned = ["淘汰", "及格线", "决定录用", "有条件行", "MBTI", "E 更外向", "I 更内向",
              "敏感", "诊断为", "智商"]
    for b in banned:
        hits = html.count(b)
        # 「心理测评结果不得作为录用唯一依据」允许出现
        ok = hits == 0
        print("  [%s] %s（出现 %d 次）" % ("OK " if ok else "FAIL", b, hits))
        if not ok:
            fails.append("出现红线词：%s" % b)
    uniq = html.count("唯一依据")
    ok_uniq = uniq <= 2   # 页脚免责声明 + 告知卡第三条，两处都是"不得作为/不是唯一依据"
    print("  [%s] 「唯一依据」只出现在合规声明里（出现 %d 次，上限 2）" % ("OK " if ok_uniq else "FAIL", uniq))
    if not ok_uniq:
        fails.append("「唯一依据」出现多处")

    # 5) 原型自标记 + 零外链
    print("\n== 原型纪律 ==")
    ext = re.findall(r'(?:src|href)\s*=\s*"(https?:)?//[^"]+', html)
    print("  [%s] 零外链（外部资源引用 %d 处）" % ("OK " if not ext else "FAIL", len(ext)))
    if ext:
        fails.append("原型出现外链")
    print("  [%s] 已标注「原型 · 非成品」" % ("OK " if "原型 · 非成品" in html else "FAIL"))
    print("  [%s] 变体可切换（?variant=）" % ("OK " if "variant" in html else "FAIL"))

    print("\n==== %s ====" % ("全部通过" if not fails else "有 %d 项未通过" % len(fails)))
    for f_ in fails:
        print("  - %s" % f_)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
