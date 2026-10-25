#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从既有产物里抽取原型要用的真实内容，输出 content.json。

不做任何设计决定，只做搬运：题面、选项、模块题量与用时口径，全部取自
第一项 / 第二项 / 第三项三份既有产物，避免原型里出现手写的假题面。

用法：python3 extract_content.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "content.json")

EQ_BANK = "/Users/leto/Documents/DSH/work/eq-test/bank/eq_bank.json"
M1_HTML = "/Users/leto/WorkBuddy/HR技术中台/outputs/云上文旅集团候选人第一项测试_20261024.html"
M3_MERGED = "/Users/leto/WorkBuddy/HR技术中台/outputs/云上文旅集团核心人才系列测试_20261024.html"


def js_const(src, name):
    """从一个 HTML/JS 文件里抠出 `const NAME = {...};` / `[...]` 的 JSON 字面量。"""
    m = re.search(r"const\s+%s\s*=\s*(\{.*?\}|\[.*?\])\s*;" % name, src, re.S)
    if not m:
        raise SystemExit("找不到 const %s" % name)
    return json.loads(m.group(1))


def main():
    with open(EQ_BANK, encoding="utf-8") as f:
        bank = json.load(f)
    with open(M1_HTML, encoding="utf-8") as f:
        m1src = f.read()
    with open(M3_MERGED, encoding="utf-8") as f:
        m3src = f.read()

    m1_questions = js_const(m1src, "QUESTIONS")
    m1_types = js_const(m1src, "TYPES")
    lg = js_const(m3src, "LG")

    sjt = bank["sjt"][0]
    self_item = bank["self_items"][0]

    content = {
        "_note": "全部取自既有产物；本文件只搬运，不新增内容。",
        "m1": {
            "title": "第一项 · 倾向测试",
            "count": "96 题",
            "minutes": "约 12 分钟",
            "count_source": "第一项独立版报告抬头：题目 96 题（四组倾向各 24 题，全部必答）",
            "minutes_source": "第一项独立版副标题：约 12 分钟",
            "sample": {
                "stem": "以下哪种描述更符合你？",
                "options": [m1_questions[0]["a"], m1_questions[0]["b"]],
            },
            "type_example": {
                "name": m1_types["INTJ"]["name"],
                "alias": m1_types["INTJ"]["alias"],
            },
        },
        "m2": {
            "title": "第二项 · 情境测试",
            "count": "16 自评 + 60 情境",
            "minutes": "约 30 分钟",
            "count_source": "题库 meta：sjt_scored 48 + sjt_consistency 12 + self_items 16",
            "minutes_source": "EQ 测评调研简报：SJT 情境 30–40 分钟",
            "sample_self": {"text": self_item["text"]},
            "sample_sjt": {
                "stem": sjt["stem"],
                "options": [sjt["options"][k] for k in ("A", "B", "C", "D")],
            },
            "dimensions": [d["name"] for d in bank["dimensions"]],
        },
        "m3": {
            "title": "第三项 · 推理测试",
            "count": "40 题 · 8 维度",
            "minutes": "建议 45 分钟",
            "count_source": "第三项施测说明：40 题（8 维度 × 5 题），全部必答",
            "minutes_source": "第三项施测说明：建议 45 分钟",
            "sample": {
                "stem": lg["questions"][0]["stem"],
                "options": lg["questions"][0]["options"],
            },
            "levels": [lv["name"] for lv in lg["levels"]],
        },
        "footer": [
            "浙江云上文旅集团 · 集团行政人事部 ｜ 本页为纯本地单文件网页，作答内容不上传服务器",
            "心理测评结果不得作为录用唯一依据；本测试不构成医学或心理诊断",
        ],
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    print("已写出 %s" % OUT)
    for key in ("m1", "m2", "m3"):
        item = content[key]
        print("  %s: %s / %s" % (key, item["count"], item["minutes"]))
    print("  第二项情境题首题：%s" % content["m2"]["sample_sjt"]["stem"][:40])


if __name__ == "__main__":
    main()
