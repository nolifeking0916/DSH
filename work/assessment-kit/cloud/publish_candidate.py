#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布「云版候选人页」的唯一入口（票 #26 · 维护者 2026-10-25 裁定 Q1=B）。

两步，缺一不可：
  1. 构建不含答案键的候选人页（build_candidate.build）；
  2. 跑发布门（verify_candidate_page）：页面里不许有锚点与判据。

上传之后的第三步（脚本代劳不了，它没有 MCP 通道）：
  manageHosting(action="upload", cloudPath="/index.html", localPath="<产物路径>", confirm=true)
  然后对**已发布的 URL** 再跑一次门：
  python3 cloud/publish_candidate.py --check-url https://.../index.html

为什么要对 URL 再跑一次：
  · 托管可能有缓存，本地过了不代表线上过了；
  · 更要紧的：**离线成品（dist/）本来就带锚点**，它是给施测人用的。
    谁要是把它直接传上公开托管，答案键就发出去了 —— 所以「上传前跑门」是硬要求。

用法：
  python3 cloud/publish_candidate.py
  python3 cloud/publish_candidate.py --check-url https://xxx/index.html
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "publish", "candidate", "index.html")


def load(name):
    spec = importlib.util.spec_from_file_location("kb_" + name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def item_gate(target):
    """跑题库门（src/verify_items.py）：逐题选项 / 判分码 + 212 道题逐题渲染。

    为什么发布门之外还要这一道：发布门只查「页面里没有答案键」，
    查不出「某一题渲染不出选项」—— 2026-10-25 真实候选人反馈「第二项第 17 题没有选项」，
    根因是 app.js 读错字段名（opts: x.options），数据一个不少、渲染一题不出。
    """
    script = os.path.join(HERE, "..", "src", "verify_items.py")
    print("")
    print("题库门检查：%s %s" % (script, target))
    return subprocess.run([sys.executable, script, target]).returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default=None, help="交卷接口地址")
    ap.add_argument("--out", default=DEFAULT_OUT, help="产物路径")
    ap.add_argument("--check-url", default=None, help="已发布页面的 URL（顺手再查一次门）")
    args = ap.parse_args()

    builder = load("build_candidate")
    endpoint = args.endpoint or builder.DEFAULT_ENDPOINT
    out_path, stripped, size = builder.build(endpoint, args.out)
    fields = sorted(set(stripped))
    print("已生成 %s（%.1f KB）" % (out_path, size / 1024))
    print("剥离的答案键字段（%d 类）：%s" % (len(fields), "、".join(fields)))
    print("交卷接口：%s" % endpoint)
    print("")

    gate = load("verify_candidate_page")
    rc = gate.check_page(out_path, verbose=True)
    if rc != 0:
        print("")
        print("发布门没过 ⇒ 不要上传这一份。")
        return rc

    # 题库门（2026-10-25 加）：逐题选项 / 判分码 + **212 道题逐题渲染**
    # —— 发布门只查「页面里没有答案键」，查不出「某一题渲染不出选项」：
    #    2026-10-25 真实候选人反馈「第二项第 17 题没有选项」，
    #    根因是 app.js 读错字段名（opts: x.options），数据一个不少、渲染一题不出。
    rc = item_gate(out_path)
    if rc != 0:
        print("")
        print("题库门没过 ⇒ 不要上传这一份。")
        return rc

    print("")
    print("下一步（上传）：")
    print("  manageHosting(action=\"upload\", cloudPath=\"/index.html\", localPath=\"%s\", confirm=true)" % out_path)
    if args.check_url:
        print("")
        rc = gate.check_page(None, args.check_url, verbose=True)
        return rc if rc != 0 else item_gate(args.check_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
