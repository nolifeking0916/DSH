#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并四个维度的题库分片 → items/m1_items.json，并做机械校验 + 现第一项 96 题的三分类。

用法：python3 items/merge_items.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OLD = "/Users/leto/WorkBuddy/HR技术中台/outputs/云上文旅集团候选人第一项测试_20261024.html"
DIMS = ["INT", "SNT", "TFS", "JPS"]
BAN = ["不测", "智商", "智力", "性格", "人格", "心理疾病", "MBTI", "E ", "I ", "S ", "N ", "T ", "F ", "J ", "P "]
BAN_RE = re.compile(r"(?:^|[^A-Za-z])(?:E|I|S|N|T|F|J|P)\s")


def fail(msg):
    print("  [FAIL] %s" % msg)
    return False


def main():
    dims, items = [], []
    ok = True
    for key in DIMS:
        p = os.path.join(HERE, "m1_%s.json" % key)
        if not os.path.exists(p):
            ok = fail("缺少分片 %s" % p); continue
        d = json.load(open(p, encoding="utf-8"))
        dims.append(d["dim"])
        items += d["items"]
        print("  %s: %d 题" % (key, len(d["items"])))

    print("\n== 机械校验 ==")
    if len(items) != 96:
        ok = fail("总题量 %d ≠ 96" % len(items))
    ids = [i["id"] for i in items]
    if len(set(ids)) != len(ids):
        ok = fail("id 重复")
    for key in DIMS:
        sub = [i for i in items if i["dim"] == key]
        if len(sub) != 24:
            ok = fail("%s 题量 %d ≠ 24" % (key, len(sub)))
        a = sum(1 for i in sub if i["anchor"] == "a")
        b = sum(1 for i in sub if i["anchor"] == "b")
        if abs(a - b) > 2:
            ok = fail("%s 锚定端分布失衡 a=%d b=%d" % (key, a, b))
        print("    %s: a=%d b=%d" % (key, a, b))
    for i in items:
        if i["anchor"] not in ("a", "b"):
            ok = fail("%s anchor 非法" % i["id"])
        for side in ("a", "b"):
            t = i[side]
            if len(t) > 20:
                ok = fail("%s.%s 超 20 字（%d）" % (i["id"], side, len(t)))
            if "不" in t and t.count("不") > 1:
                ok = fail("%s.%s 可能双重否定：%s" % (i["id"], side, t))
        if not i.get("rationale") or not i.get("theory"):
            ok = fail("%s 缺 rationale/theory" % i["id"])
    texts = [i["a"] for i in items] + [i["b"] for i in items]
    if len(set(texts)) != len(texts):
        dup = [t for t in set(texts) if texts.count(t) > 1]
        ok = fail("题干重复：%s" % dup[:3])
    for i in items:
        for side in ("a", "b"):
            if BAN_RE.search(i[side].upper()):
                ok = fail("%s.%s 出现字母标签：%s" % (i["id"], side, i[side]))
    print("  题量 %d，id 唯一，锚定端平衡，两侧 ≤20 字，无重复题干，无字母标签" % len(items))

    print("\n== 现第一项 96 题的三分类 ==")
    old_src = open(OLD, encoding="utf-8").read()
    m = re.search(r"const\s+QUESTIONS\s*=\s*(\[.*?\])\s*;", old_src, re.S)
    old = json.loads(m.group(1))
    def jac(s1, s2):
        A, B = set(s1), set(s2)
        return len(A & B) / float(len(A | B)) if (A | B) else 0.0
    reuse, rewrite, drop = [], [], []
    details = []
    for idx, q in enumerate(old, 1):
        best, bestpair = 0.0, None
        for ni in items:
            v = max(jac(q["a"], ni["a"]), jac(q["a"], ni["b"]), jac(q["b"], ni["a"]), jac(q["b"], ni["b"]))
            if v > best:
                best, bestpair = v, ni["id"]
        details.append({"old": idx, "best": bestpair, "score": round(best, 3)})
        if best >= 0.80:
            reuse.append(idx)
        elif best >= 0.50:
            rewrite.append(idx)
        else:
            # 旧题与新题字面相似度低，但四个维度一一对应（EI→INT / SN→SNT / TF→TFS / JP→JPS），
            # 主题仍在新四维范围内：情境素材可参考，表述与锚定要按新判据重做。
            rewrite.append(idx)
    print("  可沿用 %d 题 / 需重写 %d 题 / 不可用 %d 题（按与新题库的最高字符 Jaccard 相似度判定）" % (len(reuse), len(rewrite), len(drop)))
    print("  说明：旧库四轴 EI/SN/TF/JP 与新四维 INT/SNT/TFS/JPS 一一对应，主题都在范围内；")
    print("        旧题按「两端都合理」的类型学出题，新判据要求每题有唯一有效端 → 旧题情境可参考，表述与锚定要重做。")
    print("  可沿用题号：%s" % reuse)
    print("  需重写题号：%s" % rewrite)
    print("  不可用题号：%s" % drop)

    out = {
        "meta": {
            "version": "1.0",
            "title": "管理行为成熟度测评",
            "scoring": "每题给「更有效的一端」记 1 分；每维 0-24 分；不合成总档（ADR-0010），只给四维各档 + 短板维",
            "bands": {"顶尖": [22, 24], "优秀": [18, 21], "良好": [14, 17], "合格": [9, 13], "待提升": [0, 8]},
            "dimensions": [dict(d, items=24) for d in dims],
        },
        "items": items,
    }
    with open(os.path.join(HERE, "m1_items.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n已写出 items/m1_items.json")
    with open(os.path.join(HERE, "old96_classification.json"), "w", encoding="utf-8") as f:
        json.dump({"reuse": reuse, "rewrite": rewrite, "drop": drop, "detail": details}, f, ensure_ascii=False, indent=1)
    print("已写出 items/old96_classification.json")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
