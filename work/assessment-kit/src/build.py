#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把设计源内联成单文件成品，并做外链自检。

用法：python3 src/build.py
产物：dist/云上文旅集团核心人才系列测试_20261024.html（零外链、离线可用）
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
OUT_NAME = "云上文旅集团核心人才系列测试_20261024.html"
# 云上测试版（build.py --cloud）：同一套源码，注入网关路由地址，页脚与完成页走云端口径。
CLOUD_OUT_NAME = "云上文旅集团核心人才系列测试_云上测试版_20261025.html"
CLOUD_ENDPOINT = os.environ.get(
    "ASSESSMENT_CLOUD_ENDPOINT",
    "https://uu-one-d4gc4ot78a702cb70-1257197409.ap-shanghai.app.tcloudbase.com/api/assessment")
BRAND = "云上文旅集团核心人才系列测试"


def read(p, required=True):
    full = os.path.join(ROOT, p)
    if not os.path.exists(full):
        if required:
            sys.exit("缺少输入文件：%s" % p)
        return ""
    with open(full, encoding="utf-8") as f:
        return f.read()


def load_json(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return json.load(f)


def build_data():
    m1 = load_json("items/m1_items.json")
    eq = load_json("data/eq_bank_encoded.json")
    m3 = load_json("data/logic_m3.json")

    # 第二项：options 由 {A,B,C,D} 转成数组；保留 answer/second/third 字母
    sjt = []
    for q in eq["sjt"]:
        o = q.get("options") or {}
        opts = [o.get(k, "") for k in "ABCD"]
        sjt.append({
            "id": q["id"], "dimension": q["dimension"], "stem": q["stem"], "opts": opts,
            "answer": q.get("answer"), "second": q.get("second"), "third": q.get("third"),
            "scored": int(q.get("score", 0) or 0) > 0,   # 一致性检查题 score=0，不计入维度分
            "pair": q.get("pair"), "faking": bool(q.get("faking")),
            "consistency": bool(q.get("consistency")), "c": q.get("c"),
        })
    eq_out = {
        "meta": eq.get("meta", {}),
        "dimensions": eq["dimensions"],
        "self_items": eq["self_items"],
        "sjt": sjt,
    }
    return {"brand": BRAND, "m1": m1, "eq": eq_out, "m3": m3}


SHELL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>%(brand)s</title>
<style>
%(tokens)s
%(components)s
%(layout)s
</style>
</head>
<body>
<div id="app"></div>
<div class="sheet-mask" id="mask"></div>
<div class="gridpanel" id="gridpanel" role="dialog" aria-label="题号面板">
  <h4 id="grid-title">题号</h4>
  <div class="g" id="grid"></div>
  <button class="btn btn-quiet btn-full" style="margin-top:14px" onclick="APP.closeGrid()">关闭</button>
</div>
<script>
%(copy)s
</script>
<script>
window.__DATA__ = %(data)s;
</script>
<script>
%(report)s
</script>
<script>
%(app)s
</script>
</body>
</html>
"""


def app_source(cloud=False, endpoint=None):
    """app.js 的云端开关：**占位符只在这里替换一次**（单一来源）。

    教训（2026-10-25）：`cloud/build_candidate.py` 曾自己拼装页面、没走这条替换，
    于是产物里留着 `__CLOUD_ON__` ⇒ 浏览器加载即抛 ReferenceError ⇒ 整页空白。
    ⇒ 任何构建路径都必须调这个函数，不要各自 replace。
    """
    src = read("src/modules/app.js")
    src = src.replace("__CLOUD_ON__", "true" if cloud else "false")
    src = src.replace("__CLOUD_ENDPOINT__", (endpoint or CLOUD_ENDPOINT) if cloud else "")
    return src


def main():
    cloud = "--cloud" in sys.argv
    data = build_data()
    app_src = app_source(cloud=cloud)
    html = SHELL % {
        "brand": BRAND,
        "tokens": read("src/tokens.css"),
        "components": read("src/components.css"),
        "layout": read("src/layout.css"),
        "copy": read("src/data/copy.js"),
        "data": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        "report": read("src/modules/report.js"),
        "app": app_src,
    }
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, CLOUD_OUT_NAME if cloud else OUT_NAME)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    # 外链自检：成品必须零外链
    bad = []
    for pat, why in [(r'src\s*=\s*["\']https?://', "外部脚本"), (r'href\s*=\s*["\']https?://', "外部样式/链接"),
                     (r'@import', "@import"), (r'url\(\s*["\']?https?:', "外链资源"),
                     (r'@font-face', "外部字体"), (r'<link\b', "link 标签")]:
        if re.search(pat, html, re.I):
            bad.append(why)
    size = os.path.getsize(out)
    print("已生成 %s（%.1f KB）" % (out, size / 1024))
    print("题量：m1=%d / eq 自评 %d + 情境 %d / m3=%d" %
          (len(data["m1"]["items"]), len(data["eq"]["self_items"]), len(data["eq"]["sjt"]), len(data["m3"]["questions"])))
    if bad:
        print("自检未通过：成品出现外链 -> %s" % "、".join(bad))
        sys.exit(1)
    if cloud:
        print("自检通过：零外链资源（本版会向 %s 提交作答）" % CLOUD_ENDPOINT)
    else:
        print("自检通过：零外链，可离线打开")


if __name__ == "__main__":
    main()
