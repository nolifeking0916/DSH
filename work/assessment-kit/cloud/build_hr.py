#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建「施测人汇总台」（票 #45 · 施测人侧落地）。

与候选人页**同一套外壳**：同一份 report.js（施测人报告渲染器）、同一份固定文案
（copy.js）、同一套设计系统（tokens / components / layout），内嵌数据用**去答案键**
的那份（复用 cloud/build_candidate.py 的 sanitize）—— 汇总台不需要题库锚点，
也不该把答案键发到任何浏览器里。

产物：cloud/publish/hr/index.html（自包含单文件、零外链），
放到静态托管的 **/hr/** 路径下（票 #36 Q5：不绑自定义域）。

构建完自动跑 cloud/verify_hr_page.py（发布门）：
  · 内嵌数据里没有答案键字段；
  · 判据原文与推理题解析一个字都不出现（与候选人页同一批金丝雀）；
  · 零外链资源；
  · 页面脚本里**没有 m1_raw**（逐题作答不进汇总台，票 #45 的硬约束）；
  · headless Chrome 实跑：控制台不许报错，DOM 里要有首屏文案。

用法：
  python3 cloud/build_hr.py
  python3 cloud/build_hr.py --endpoint URL --out 路径
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DEFAULT_ENDPOINT = "https://uu-one-d4gc4ot78a702cb70-1257197409.ap-shanghai.app.tcloudbase.com/api/assessment"
DEFAULT_OUT = os.path.join(HERE, "publish", "hr", "index.html")

# 汇总台自己的骨架。样式分两块：
#   · {{CSS}}      = 设计系统（tokens + components + layout）—— 报告渲染要靠它，
#                     同时也是「下载报告 HTML」时内联进去的那一块；
#   · {{DASH}}    = 汇总台自己的少量样式（表格 / 面板）。
SHELL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>施测人汇总台 · 云上文旅集团核心人才系列测试</title>
<style id="page-css">
{{CSS}}
</style>
<style>
{{DASH}}
</style>
</head>
<body>
<div class="hr-wrap">
  <header class="hr-head">
    <h1>施测人汇总台</h1>
    <p class="hint" id="hrlead"></p>
    <p class="note warnline">本轮是<strong>自测期</strong>：这一页<strong>没有鉴权</strong> ——
      任何拿到这个地址的人都能看全部结果并导出（维护者已知的取舍，票 #36 决议）；
      等被测对象变成外部候选人或公开链接分发时再开鉴权（票 #44）。</p>
  </header>

  <section class="card">
    <div class="toolbar">
      <label class="field"><span>最近</span>
        <select id="limit">
          <option value="25">25 份</option>
          <option value="50" selected>50 份</option>
          <option value="100">100 份</option>
          <option value="200">200 份</option>
        </select>
      </label>
      <button class="btn btn-quiet" id="refresh">刷新列表</button>
      <label class="field grow"><span>按测评编号直达一份</span>
        <input id="code" placeholder="EQ-20261025-XXXXXX-XXXX" autocomplete="off">
      </label>
      <button class="btn btn-primary" id="go">直达</button>
    </div>
    <p class="note" id="note"></p>
    <div class="tablewrap"><table class="hr-table" id="rows"></table></div>
    <p class="hint">默认列按票 #36 的决议：姓名 / 测评编号 / 组 / 岗位层级 / 等级 / 提交时间 / 时长 / 未答题数。
      <b>身份证后 4 位</b>不在默认列里，只在接口返回与导出文件里（供这一轮人工核对）。
      <b>组</b>与<b>岗位层级</b>目前是空的 —— 候选人页只收姓名与身份证。</p>
  </section>

  <section class="card" id="one-panel" hidden>
    <h2>那一份的报告</h2>
    <table class="kv" id="one-meta"></table>
    <div class="row"><button class="btn btn-quiet" id="dl-report">下载这份报告（HTML · 可直接打印成 PDF）</button></div>
    <div id="report"></div>
  </section>

  <section class="card">
    <h2>一键导出</h2>
    <div class="row">
      <button class="btn btn-primary" id="export-batch">导出这一批的汇总</button>
      <button class="btn btn-quiet" id="dl-csv">下载汇总 CSV</button>
      <button class="btn btn-quiet" id="dl-json">下载分析用 JSON（可直接喂 pilot/analyze.py --real）</button>
    </div>
    <div class="distrow" id="dist"></div>
    <p class="hint">深度统计（α / 分半 / 极端题）走既有离线管线：下载「分析用 JSON」后跑
      <code>python3 pilot/analyze.py --real &lt;文件&gt;</code>。
      有未答完的份子不进管线（管线的 0/1 形状放不下「未作答」，硬塞会把分压低），
      会单独列在 JSON 的 <code>excluded</code> 里。</p>
  </section>

  <footer class="foot" id="foot"></footer>
</div>
<script>
{{COPY}}
</script>
<script>
window.__DATA__ = {{DATA}};
</script>
<script>
{{REPORT}}
</script>
<script>
{{APP}}
</script>
<script>
/* 页脚用**云上版**措辞（copy.js 的 footCloud）：这一页与它出的报告都是从服务器上的
   记录生成的，「不上传服务器」那句只属于离线版（copy.js 注释原话）。
   候选人页的页脚口径由票 #37 统一重写，本页只保证自己不说假话。 */
window.__COPY__.foot = window.__COPY__.footCloud;
document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("foot").innerHTML = window.__COPY__.foot.map(function (f) { return "<b>" + f + "</b>"; }).join("");
  document.getElementById("hrlead").textContent = window.__COPY__.hrLead;
});
</script>
</body>
</html>
"""

DASH = """
.hr-wrap { max-width: 1000px; margin: 0 auto; padding: var(--sp-4) var(--sp-3) var(--sp-6); }
.hr-head h1 { font-size: var(--fs-1); margin: 0 0 var(--sp-2); }
.hr-wrap .card { margin: var(--sp-3) 0; padding: var(--sp-4); }
.hr-wrap h2 { font-size: var(--fs-2); margin: 0 0 var(--sp-2); }
.toolbar { display: flex; flex-wrap: wrap; gap: var(--sp-2); align-items: flex-end; }
.toolbar .field { margin: 0; }
.toolbar .grow { flex: 1 1 260px; }
.toolbar input, .toolbar select { width: 100%; }
.note { color: var(--text-2, #666); font-size: var(--fs-2); margin: var(--sp-2) 0; }
.note.bad { color: #b3261e; }
.warnline { border-left: 3px solid #b3261e; padding-left: var(--sp-2); }
.tablewrap { overflow-x: auto; }
.hr-table { width: 100%; border-collapse: collapse; font-size: var(--fs-2); }
.hr-table th, .hr-table td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line, #e3e3e6); white-space: nowrap; }
.hr-table th { font-weight: 600; color: var(--text-2, #555); }
.mono { font-family: ui-monospace, Menlo, monospace; font-size: 0.95em; }
.row { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin: var(--sp-2) 0; }
.kv { width: 100%; border-collapse: collapse; font-size: var(--fs-2); margin: var(--sp-2) 0; }
.kv th { text-align: left; color: var(--text-2, #555); font-weight: 500; padding: 4px 10px 4px 0; white-space: nowrap; }
.kv td { padding: 4px 16px 4px 0; }
.distrow { display: flex; flex-wrap: wrap; gap: var(--sp-3); margin: var(--sp-2) 0; }
.dist h4 { margin: 0 0 4px; font-size: var(--fs-2); }
.dist table { border-collapse: collapse; font-size: var(--fs-2); }
.dist td { padding: 2px 10px 2px 0; }
#report { margin-top: var(--sp-3); }
"""


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(endpoint, out_path):
    kb = load_module(os.path.join(ROOT, "src", "build.py"), "kb_build")
    cand = load_module(os.path.join(HERE, "build_candidate.py"), "kb_candidate")

    data = kb.build_data()
    clean, stripped = cand.sanitize(data)

    with open(os.path.join(HERE, "hr_runtime.js"), encoding="utf-8") as f:
        runtime = f.read()
    if "__ENDPOINT__" not in runtime:
        sys.exit("hr_runtime.js 里找不到 __ENDPOINT__ 占位符")
    runtime = runtime.replace("__ENDPOINT__", endpoint)

    css = "\n".join([kb.read("src/tokens.css"), kb.read("src/components.css"), kb.read("src/layout.css")])

    html = SHELL
    for key, value in [
        ("{{CSS}}", css),
        ("{{DASH}}", DASH),
        ("{{COPY}}", kb.read("src/data/copy.js")),
        ("{{DATA}}", json.dumps(clean, ensure_ascii=False, separators=(",", ":"))),
        ("{{REPORT}}", kb.read("src/modules/report.js")),
        ("{{APP}}", runtime),
    ]:
        html = html.replace(key, value)

    if "__ENDPOINT__" in html or "__CLOUD_ON__" in html:
        sys.exit("构建失败：产物里还有占位符（浏览器会直接抛错、整页空白）")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path, stripped, len(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="云函数地址")
    ap.add_argument("--out", default=DEFAULT_OUT, help="产物路径")
    ap.add_argument("--skip-gate", action="store_true", help="跳过发布门（不建议）")
    args = ap.parse_args()

    out, stripped, size = build(args.endpoint, args.out)
    print("已生成 %s（%.1f KB）" % (out, size / 1024))
    print("剥离的答案键字段（%d 类）：%s" % (len(set(stripped)), "、".join(sorted(set(stripped)))))
    print("取数接口：%s" % args.endpoint)

    if args.skip_gate:
        print("（已跳过发布门）")
        return 0

    gate = load_module(os.path.join(HERE, "verify_hr_page.py"), "kb_hr_gate")
    return gate.check_page(out, verbose=True)


if __name__ == "__main__":
    raise SystemExit(main())
