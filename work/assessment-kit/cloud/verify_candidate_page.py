#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布门：候选人页不许带答案键（票 #26 · 维护者 2026-10-25 裁定 Q1=B）。

这道门是真人数据有效性的最后一道保险：
  · 题目答案一旦进了候选人浏览器，那一批作答就整批作废（α 趋近 1、分布退化、
    异常盲检同时失效），而且不能靠事后分析挽救。
  · 所以「发链接」这一步必须先过门。

查两遍，两遍都过才算过：
  1. 结构检查：内嵌数据里不许出现承载答案的字段（anchor / rationale / answer ...）。
  2. 金丝雀检查：把题库里每条判据释义与推理题解析当金丝雀，
     它们一个字都不许出现在页面里 —— 哪怕字段改了名也拦得住。

另外查：没有外链资源（script/link/@import/@font-face/外链 url）、交卷运行时在位。

用法：
  python3 cloud/verify_candidate_page.py --page cloud/publish/index.html
  python3 cloud/verify_candidate_page.py --url https://.../index.html   # 查已发布的页面
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

Q = chr(34) + chr(39)          # 两种引号，用来拼正则（避免在源码里写转义引号）

# 内嵌数据里不许出现的字段（按位置判定）
FORBIDDEN = {
    "m1.items": ("anchor", "rationale", "theory"),
    "eq.sjt": ("answer", "second", "third", "c"),
    "m3.questions": ("answer", "explain"),
}


def load_build_module():
    path = os.path.join(ROOT, "src", "build.py")
    spec = importlib.util.spec_from_file_location("kb_build", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fetch_page(path=None, url=None):
    if url:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.read().decode("utf-8", "replace"), url
    with open(path, encoding="utf-8") as f:
        return f.read(), os.path.abspath(path)


def extract_data(html):
    m = re.search(r"window\.__DATA__\s*=\s*(\{[\s\S]*?\});\s*</script>", html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def check_page(path=None, url=None, verbose=True):
    html, origin = fetch_page(path, url)
    problems = []

    # 1. 结构检查
    data = extract_data(html)
    if data is None:
        problems.append("页面里找不到 window.__DATA__（不是本构建的页面？）")
    else:
        for loc, fields in FORBIDDEN.items():
            node = data
            for p in loc.split("."):
                node = (node or {}).get(p, []) if isinstance(node, dict) else []
            for item in (node or []):
                if not isinstance(item, dict):
                    continue
                for f in fields:
                    if f in item:
                        problems.append("内嵌数据 %s 里仍有字段 %s" % (loc, f))
        if "readme" in (data.get("eq") or {}):
            problems.append("内嵌数据 eq.readme 仍在（开发者说明，可能带答案示例）")

    # 2. 金丝雀检查：判据释义与推理题解析一个字都不许出现
    src = load_build_module().build_data()
    canaries = []
    for it in src["m1"]["items"]:
        if it.get("rationale"):
            canaries.append(("m1:" + it["id"], it["rationale"]))
    for q in src["m3"]["questions"]:
        if q.get("explain"):
            canaries.append(("m3:" + q["id"], q["explain"]))
    hit = 0
    for tag, text in canaries:
        probe = text[:24]
        if probe and probe in html:
            problems.append("页面里出现了判据原文（%s）：%s" % (tag, probe))
            hit += 1
            if hit >= 5:
                problems.append("（更多同类命中已省略）")
                break

    # 3. 外链资源（交卷接口那个 URL 是允许的，它是 fetch 的目标不是资源）
    ext = [
        (r"<script[^>]*src\s*=\s*[" + Q + r"]https?://", "外部脚本"),
        (r"<link\b", "link 标签"),
        (r"@import", "@import"),
        (r"url\(\s*[" + Q + r"]?https?:", "外链资源"),
        (r"@font-face", "外部字体"),
    ]
    for pat, why in ext:
        if re.search(pat, html, re.I):
            problems.append("出现外链资源（%s）" % why)

    # 4. 交卷运行时在位
    if "__cloudRetry" not in html or "m1_raw" not in html:
        problems.append("交卷运行时不在页面里（交卷写库会失效）")

    if verbose:
        print("发布门检查：%s" % origin)
        print("  金丝雀 %d 条（96 条判据原文 + 40 条推理题解析）" % len(canaries))
    if problems:
        print("  不通过：")
        for p in problems:
            print("    - %s" % p)
        return 1
    if verbose:
        print("  通过：页面不含答案键、无外链资源、交卷运行时在位")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="本地页面路径")
    ap.add_argument("--url", help="已发布的页面 URL")
    args = ap.parse_args()
    if not args.page and not args.url:
        ap.error("要给 --page 或 --url")
    return check_page(args.page, args.url)


if __name__ == "__main__":
    raise SystemExit(main())
