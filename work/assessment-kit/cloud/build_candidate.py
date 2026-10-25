#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建「云版候选人页」（票 #26 · 维护者 2026-10-25 裁定 Q1=B）。

与离线成品的区别只有一处，但它是致命的：**候选人页里没有题库锚点与判据**。

  · 离线成品（dist/）：施测人用，含锚点与完整计分；不要公开分发。
  · 候选人页（cloud/publish/index.html）：公开分发，只有题面与两栏；
    分数由云函数算（cloud/functions/assessment/score.js）。

做法：复用 src/build.py 的同一套外壳与样式，只把内嵌数据换成**去掉答案键**的那份，
并注入 cloud/candidate_runtime.js（交卷写库）。

构建完自动跑 cloud/verify_candidate_page.py（发布门）：门不过就不许发链接。
这一道门是 #26 的数据有效性的最后一道保险。

用法：
  python3 cloud/build_candidate.py                     # 构建 + 跑发布门
  python3 cloud/build_candidate.py --endpoint URL      # 换交卷接口地址
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DEFAULT_ENDPOINT = "https://uu-one-d4gc4ot78a702cb70-1257197409.ap-shanghai.app.tcloudbase.com/api/assessment"


def load_build_module():
    path = os.path.join(ROOT, "src", "build.py")
    spec = importlib.util.spec_from_file_location("kb_build", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sanitize(data):
    """去掉所有「答案键」字段，返回 (净化后的数据, 剥离清单)。

    剥离清单是给人看的：发布前要能一眼确认「键都走了」。
    """
    stripped = []
    out = json.loads(json.dumps(data, ensure_ascii=False))

    for it in out["m1"]["items"]:
        for k in ("anchor", "rationale", "theory"):
            if k in it:
                it.pop(k)
                stripped.append("m1.items." + k)
    for x in out["eq"]["sjt"]:
        for k in ("answer", "second", "third", "c"):
            if k in x:
                x.pop(k)
                stripped.append("eq.sjt." + k)
    if "readme" in out["eq"]:
        out["eq"].pop("readme")
        stripped.append("eq.readme")
    for q in out["m3"]["questions"]:
        for k in ("answer", "explain"):
            if k in q:
                q.pop(k)
                stripped.append("m3.questions." + k)
    return out, stripped


def build(endpoint, out_path):
    kb = load_build_module()
    data = kb.build_data()
    clean, stripped = sanitize(data)

    rt_path = os.path.join(HERE, "candidate_runtime.js")
    with open(rt_path, encoding="utf-8") as f:
        runtime = f.read()
    if "__ENDPOINT__" not in runtime:
        sys.exit("candidate_runtime.js 里找不到 __ENDPOINT__ 占位符")
    runtime = runtime.replace("__ENDPOINT__", endpoint)

    old = "<script>\n%(app)s\n</script>"
    new = "<script>\n%(app)s\n</script>\n<script>\n%(cand)s\n</script>"
    shell = kb.SHELL.replace(old, new)
    html = shell % {
        "brand": kb.BRAND,
        "tokens": kb.read("src/tokens.css"),
        "components": kb.read("src/components.css"),
        "layout": kb.read("src/layout.css"),
        "copy": kb.read("src/data/copy.js"),
        "data": json.dumps(clean, ensure_ascii=False, separators=(",", ":")),
        "report": kb.read("src/modules/report.js"),
        "app": kb.read("src/modules/app.js"),
        "cand": runtime,
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path, stripped, len(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="交卷接口地址")
    ap.add_argument("--out", default=os.path.join(HERE, "publish", "candidate", "index.html"), help="产物路径")
    ap.add_argument("--skip-gate", action="store_true", help="跳过发布门（不建议）")
    args = ap.parse_args()

    out, stripped, size = build(args.endpoint, args.out)
    fields = sorted(set(stripped))
    print("已生成 %s（%.1f KB）" % (out, size / 1024))
    print("剥离的答案键字段（%d 类）：%s" % (len(fields), "、".join(fields)))
    print("交卷接口：%s" % args.endpoint)

    if args.skip_gate:
        print("（已跳过发布门）")
        return 0

    spec = importlib.util.spec_from_file_location("kb_gate", os.path.join(HERE, "verify_candidate_page.py"))
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate.check_page(out, verbose=True)


if __name__ == "__main__":
    raise SystemExit(main())
