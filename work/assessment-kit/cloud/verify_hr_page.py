#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布门：施测人汇总台（票 #45）。

汇总台这一页的发布门与候选人页**同源、但多两条**：

  1. 内嵌数据里没有答案键字段（与候选人页同一套 sanitize）；
  2. 判据原文与推理题解析一个字都不出现（与候选人页同一批金丝雀，136 条）；
  3. 零外链资源；
  4. **内嵌数据里不许出现逐题作答字段** —— 汇总台只显示汇总列与分数档；
     渲染器源码可以引用字段名，但真实作答不进汇总台；
  5. 占位符必须已替换（空白页事故的第一现场）；
  6. headless Chrome 实跑：控制台不许报错，DOM 里要有首屏文案。

用法：
  python3 cloud/verify_hr_page.py --page cloud/publish/hr/index.html
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V = load_module(os.path.join(HERE, "verify_candidate_page.py"), "kb_cand_gate")


RAW_ANSWER_FIELDS = {"m1_raw", "m2_answers", "m3_answers"}


def raw_answer_fields(value, path="$"):
    """递归返回内嵌 JSON 中的逐题字段路径；不扫描渲染器源码字符串。"""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = path + "." + str(key)
            if key in RAW_ANSWER_FIELDS:
                found.append(child)
            found.extend(raw_answer_fields(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(raw_answer_fields(item, path + "[" + str(index) + "]"))
    return found


def check_render(path, verbose=True):
    """渲染检查：静态检查看不出 JS 语法错误（空白页事故就是这么漏过去的）。"""
    problems = []
    chrome = V.find_chrome()
    if not chrome:
        if verbose:
            print("  渲染检查：跳过（没找到 Chrome）")
        return problems
    with tempfile.TemporaryDirectory() as td:
        cmd = [chrome, "--headless=new", "--disable-gpu", "--enable-logging=stderr",
               "--virtual-time-budget=5000", "--dump-dom", "file://" + os.path.abspath(path)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return ["渲染检查超时（headless Chrome 没跑完）"]
        dom = p.stdout or ""
        errs = [l for l in (p.stderr or "").splitlines()
                if "INFO:CONSOLE" in l and re.search(r"Uncaught|SyntaxError|ReferenceError|TypeError", l)]
        if errs:
            problems.append("渲染时 JS 报错 %d 条；第一条：%s" % (len(errs), errs[0][:200]))
        if "施测人汇总台" not in dom:
            problems.append("渲染后 DOM 里没有首屏文案（页面没画出来，多半是脚本崩了）")
    if verbose:
        print("  渲染检查：%s" % ("通过" if not problems else "不通过"))
    return problems


def check_page(path, verbose=True):
    html, origin = V.fetch_page(path=path, url=None)
    problems = []

    # 1. 结构检查：内嵌数据里不许有承载答案的字段
    data = V.extract_data(html)
    if data is None:
        problems.append("页面里找不到 window.__DATA__（不是本构建的页面？）")
    else:
        for loc, fields in V.FORBIDDEN.items():
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

    # 2. 金丝雀：判据原文与推理题解析一个字都不许出现
    src = V.load_build_module().build_data()
    canaries = []
    for it in src["m1"]["items"]:
        if it.get("rationale"):
            canaries.append(("m1:" + it["id"], it["rationale"]))
    for q in src["m3"]["questions"]:
        if q.get("explain"):
            canaries.append(("m3:" + q["id"], q["explain"]))
    for tag, text in canaries:
        probe = text[:24]
        if probe and probe in html:
            problems.append("页面里出现了判据原文（%s）：%s" % (tag, probe))
            break

    # 3. 外链资源
    ext = [
        (r"<script[^>]*src\s*=\s*[" + V.Q + r"]https?://", "外部脚本"),
        (r"<link\b", "link 标签"),
        (r"@import", "@import"),
        (r"url\(\s*[" + V.Q + r"]?https?:", "外链资源"),
        (r"@font-face", "外部字体"),
    ]
    for pat, why in ext:
        if re.search(pat, html, re.I):
            problems.append("出现外链资源（%s）" % why)

    # 4. 逐题作答不许进**内嵌数据**。报告渲染器的源码会合法引用 m1_raw，
    # 不能再用全文字符串匹配把代码误判为真实作答载荷。
    data_match = re.search(r"window\.__DATA__\s*=\s*(.*?);\s*</script>", html, re.S)
    if not data_match:
        problems.append("找不到 window.__DATA__ 内嵌数据，无法核验逐题字段")
    else:
        try:
            embedded = json.loads(data_match.group(1))
            raw_fields = sorted(raw_answer_fields(embedded))
            if raw_fields:
                problems.append("内嵌数据出现逐题作答字段：" + "、".join(raw_fields[:10]))
        except (TypeError, ValueError) as exc:
            problems.append("window.__DATA__ 不是合法 JSON：" + str(exc))

    # 5. 占位符必须已替换
    if "__ENDPOINT__" in html or "__CLOUD_ON__" in html:
        problems.append("页面里还有占位符 —— 浏览器会直接抛错、整页空白")

    # 6. 取数接口在位
    if "/api/assessment" not in html:
        problems.append("页面里找不到取数接口地址（云函数地址没注入？）")

    # 7. 渲染检查
    problems.extend(check_render(path, verbose=verbose))

    if verbose:
        print("发布门检查：%s" % origin)
        print("  金丝雀 %d 条（96 条判据原文 + 40 条推理题解析）" % len(canaries))
    if problems:
        if verbose:
            for pr in problems:
                print("  ✗ " + pr)
            print("发布门**不通过**")
        return 1
    if verbose:
        print("发布门**通过** ✓")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=os.path.join(HERE, "publish", "hr", "index.html"))
    args = ap.parse_args()
    return check_page(args.page, verbose=True)


if __name__ == "__main__":
    raise SystemExit(main())
