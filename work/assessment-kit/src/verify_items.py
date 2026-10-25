#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题库与判分码全量核查门（2026-10-25 立项）。

为什么有这道门
--------------
2026-10-25 真实候选人反馈：**「第二项第 17 题没有选项」**。
根因在数据，不在渲染：
  · `data/eq_bank_encoded.json` 里有的情境题 `options` 少了某个键；
  · `src/build.py` 用 `[o.get(k, "") for k in "ABCD"]` 转数组 ⇒ **缺的键变成空字符串**，
    页面上那一栏于是是空的（渲染层完全照实画，空的就被画成空的）。
**旧门全都看不出来**：它们查结构、查正则、查截图，没有一处**一道题一道题地核**。

这道门核两侧
------------
  1. **成品里内嵌的 `window.__DATA__`**（候选人实际看到的那份）—— 选项、题干、维度、判分码；
  2. **题库源文件**（同样的检查在源头跑一遍，报错能指到具体文件）。

用法
----
  python3 src/verify_items.py                       # 默认核 dist 成品
  python3 src/verify_items.py <产物路径|URL>        # 核指定产物（云版页面没有判分码，只核选项与维度）
  python3 src/verify_items.py --source-only         # 只核题库源文件

退出码 0 = 全绿；非 0 = 逐条打印未通过项。
"""
from __future__ import annotations

import collections
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
DEFAULT_PRODUCT = os.path.join(DIST, "云上文旅集团核心人才系列测试_20261024.html")

LETTERS = "ABCD"


def read_html(path):
    """取产物正文：本地路径或线上 URL 都行。"""
    if path.startswith("http"):
        req = urllib.request.Request(path, headers={"User-Agent": "verify-items"})
        return urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "ignore")
    return open(path, encoding="utf-8").read()


def extract_data(html):
    """从成品 HTML 里取出内嵌的 window.__DATA__。"""
    i = html.find("window.__DATA__")
    if i < 0:
        raise SystemExit("产物里找不到 window.__DATA__：%s" % path)
    j = html.find("{", i)
    data, _ = json.JSONDecoder().raw_decode(html[j:])
    return data


def check(data, tag, fails):
    def bad(msg):
        fails.append("[%s] %s" % (tag, msg))

    # ---------------- 第一项：96 道二极对比 ----------------
    m1 = data.get("m1", {})
    items = m1.get("items", [])
    if len(items) != 96:
        bad("第一项题量 %d ≠ 96" % len(items))
    dims = collections.Counter()
    ids = collections.Counter()
    for it in items:
        iid = it.get("i", it.get("id"))
        ids[iid] += 1
        for side in ("a", "b"):
            if not str(it.get(side, "")).strip():
                bad("第一项第 %s 题的「%s 侧」选项是空的" % (iid, side))
        if it.get("anchor") is not None and it.get("anchor") not in ("a", "b"):
            bad("第一项第 %s 题的锚定端非法：%r" % (iid, it.get("anchor")))
        # 云版候选人页**故意**剥掉锚点与判据码 ⇒ 全部没有 anchor 属正常，只在这时跳过该项
        if not str(it.get("dim", "")).strip():
            bad("第一项第 %s 题缺维度" % iid)
        else:
            dims[it["dim"]] += 1
    for k, v in ids.items():
        if v > 1:
            bad("第一项题号重复：%s（%d 次）" % (k, v))
    for dim, n in sorted(dims.items()):
        if n != 24:
            bad("第一项维度 %s 题量 %d ≠ 24" % (dim, n))

    # ---------------- 第二项：16 道自评 + 60 道情境 ----------------
    eq = data.get("eq", {})
    raw_dims = eq.get("dimensions", [])
    if isinstance(raw_dims, dict):
        edims = set(raw_dims.keys())
    else:
        edims = {d.get("key") or d.get("id") or d.get("code") for d in raw_dims}
    si = eq.get("self_items", [])
    sj = eq.get("sjt", [])
    if len(si) != 16:
        bad("第二项自评题量 %d ≠ 16" % len(si))
    sids = collections.Counter(x.get("id") for x in si)
    for x in si:
        if not str(x.get("text", "")).strip():
            bad("第二项自评 %s 题干是空的" % x.get("id"))
        if edims and x.get("dimension") not in edims:
            bad("第二项自评 %s 维度非法：%r" % (x.get("id"), x.get("dimension")))
    for k, v in sids.items():
        if v > 1:
            bad("第二项自评题号重复：%s" % k)

    if len(sj) != 60:
        bad("第二项情境题量 %d ≠ 60" % len(sj))
    jids = collections.Counter(x.get("id") for x in sj)
    for k, v in jids.items():
        if v > 1:
            bad("第二项情境题号重复：%s（%d 次）" % (k, v))
    per_dim = collections.Counter()
    consistency = 0
    for n, x in enumerate(sj, start=1):
        iid = x.get("id")
        opts = x.get("opts")
        if not isinstance(opts, list):
            bad("第二项第 %d 题（%s）没有选项数组" % (n, iid))
            opts = []
        elif len(opts) != 4:
            bad("第二项第 %d 题（%s）选项数 %d ≠ 4" % (n, iid, len(opts)))
        for k, v in enumerate(opts):
            if not str(v or "").strip():
                bad("第二项第 %d 题（%s）第 %s 栏是空的" % (n, iid, LETTERS[k] if k < 4 else k + 1))
        if not str(x.get("stem", "")).strip():
            bad("第二项第 %d 题（%s）题干是空的" % (n, iid))
        if edims and x.get("dimension") not in edims:
            bad("第二项第 %d 题（%s）维度非法：%r" % (n, iid, x.get("dimension")))
        # 判分码
        has_codes = any(x.get(f) for f in ("answer", "second", "third"))
        for f in ("answer", "second", "third"):
            v = x.get(f)
            if v is None:
                continue
            if v not in LETTERS:
                bad("第二项第 %d 题（%s）的 %s 非法：%r" % (n, iid, f, v))
                continue
            # 判分码指向的那一栏不能是空的
            if 0 <= LETTERS.index(v) < len(opts) and not str(opts[LETTERS.index(v)] or "").strip():
                bad("第二项第 %d 题（%s）的 %s=%s 指向的是**空栏**" % (n, iid, f, v))
        if x.get("answer") and x.get("second") == x.get("answer"):
            bad("第二项第 %d 题（%s）second 与 answer 相同（%s）" % (n, iid, x.get("answer")))
        if has_codes and x.get("scored", True) and not x.get("consistency"):
            per_dim[x.get("dimension")] += 1
        if x.get("consistency"):
            consistency += 1
    for dim, n in sorted(per_dim.items()):
        if n != 6:
            bad("第二项维度 %s 的计分题 %d 题 ≠ 6" % (dim, n))
    if consistency not in (0, 12):
        bad("第二项一致性题 %d 道（应为 12 道 = 6 对）" % consistency)

    # ---------------- 第三项：40 道推理 ----------------
    m3 = data.get("m3", {})
    qs = m3.get("questions", [])
    if len(qs) != 40:
        bad("第三项题量 %d ≠ 40" % len(qs))
    qids = collections.Counter(q.get("id") for q in qs)
    for k, v in qids.items():
        if v > 1:
            bad("第三项题号重复：%s" % k)
    m3dims = collections.Counter()
    for n, q in enumerate(qs, start=1):
        qid = q.get("id")
        opts = q.get("options") or []
        if not isinstance(opts, list) or not opts:
            bad("第三项第 %d 题（%s）没有选项" % (n, qid))
            opts = []
        for k, v in enumerate(opts):
            if not str(v or "").strip():
                bad("第三项第 %d 题（%s）第 %d 个选项是空的" % (n, qid, k + 1))
        a = q.get("answer")
        if a is not None:
            if not isinstance(a, int) or not (0 <= a < len(opts)):
                bad("第三项第 %d 题（%s）的 answer 越界：%r（选项 %d 个）" % (n, qid, a, len(opts)))
        if str(q.get("dim", "")).strip():
            m3dims[q["dim"]] += 1
    for dim, n in sorted(m3dims.items()):
        if n != 5:
            bad("第三项维度 %s 题量 %d ≠ 5" % (dim, n))


def audit_source(fails):
    """题库源文件侧（同一套检查，报错指到源文件）。"""
    for rel, keys in (("items/m1_items.json", None),
                      ("data/eq_bank_encoded.json", None),
                      ("data/logic_m3.json", None)):
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            fails.append("[源] 缺文件：%s" % rel)
            continue
        json.load(open(p, encoding="utf-8"))
    eq = json.load(open(os.path.join(ROOT, "data/eq_bank_encoded.json"), encoding="utf-8"))
    for n, q in enumerate(eq.get("sjt", []), start=1):
        o = q.get("options")
        if not isinstance(o, dict):
            fails.append("[源] 情境第 %d 题（%s）的 options 不是字典：%r" % (n, q.get("id"), type(o).__name__))
            continue
        missing = [k for k in LETTERS if not str(o.get(k, "") or "").strip()]
        extra = [k for k in o if k not in LETTERS]
        if missing:
            fails.append("[源] 情境第 %d 题（%s）options 缺 %s" % (n, q.get("id"), "/".join(missing)))
        if extra:
            fails.append("[源] 情境第 %d 题（%s）options 有多余键 %s" % (n, q.get("id"), "/".join(extra)))
        for f in ("answer", "second", "third"):
            v = q.get(f)
            if v is not None and v not in LETTERS:
                fails.append("[源] 情境第 %d 题（%s）的 %s 非法：%r" % (n, q.get("id"), f, v))


CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

RENDER_JS = """
<script>window.addEventListener('load',function(){setTimeout(function(){
 try{
  var S=APP.S(); var bad=[]; var n=0;
  var mods=[['m1',96],['m2',76],['m3',40]];
  mods.forEach(function(m){
    var mk=m[0], total=m[1];
    for(var i=0;i<total;i++){
      S.mod=mk; S.cur[mk]=i; APP.go('quiz');
      var opts=document.querySelectorAll('.opts .opt').length;
      var segs=document.querySelectorAll('.scale .seg').length;
      var want=(mk==='m1')?2:((mk==='m2'&&i<16)?7:4);
      var got=opts||segs;
      n++;
      if(got!==want) bad.push(mk+(i+1)+'('+got+'/'+want+')');
    }
  });
  document.title='R:'+n+':B:'+bad.length+':'+bad.slice(0,40).join(',');
 }catch(e){document.title='ERR:'+e.message;}
},600);});</script>
"""


def render_check(html, fails):
    """渲染侧：**每一道题都必须渲染出选项**（2026-10-25 加）。

    为什么数据全对还会坏：真实候选人反馈「第二项第 17 题没有选项」，
    根因是 `app.js` 读错了字段名（`opts: x.options`，而 build.py 写的是 `opts`）
    ⇒ 数据里 60 道情境题的选项一个都没少，**渲染时却一题都没画出来**
    （自评 16 题走七级量表分支，所以卡在第 17 题才暴露）。
    ⇒ 只有真的把 212 道题逐题渲染一遍、数一遍按钮，才抓得到这种错。
    """
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html.rsplit("</body>", 1)[0] + RENDER_JS + "</body></html>")
        tmp = f.name
    try:
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=30000",
                              "--dump-dom", "file://" + tmp],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=180).stdout.decode("utf-8", "ignore")
    finally:
        os.unlink(tmp)
    m = re.search(r"<title>([^<]*)</title>", dom)
    title = (m.group(1) if m else "").replace("&gt;", ">")
    mm = re.search(r"R:(\d+):B:(\d+):(.*)", title)
    if not mm:
        fails.append("[渲染] 逐题渲染自检没跑起来（%s）" % (title or "无回读"))
        return
    total, nbad, detail = int(mm.group(1)), int(mm.group(2)), mm.group(3)
    if nbad:
        fails.append("[渲染] %d / %d 道题渲染出的选项数不对（题号(实得/应有)）：%s" % (nbad, total, detail))
    else:
        print("  逐题渲染：%d 道题全部渲染出应有数量的选项 ✓" % total)



FLOW_JS = """
<script>
window.__muts = 0; window.__fetches = 0; window.__errs = [];
window.fetch = function (u, o) {
  if (o && o.method === 'POST') window.__fetches++;   // 只数「交卷」；查重用的 GET 不算
  return Promise.reject(new Error('blocked-by-gate'));
};
window.addEventListener('error', function (e) { window.__errs.push(String(e.message || '')); });
window.addEventListener('load', function () { setTimeout(function () {
 try {
  var S = APP.S();
  S.consented = true; S.name = '门禁'; S.idLast4 = '0000';
  S.mod = 'm3'; S.cur.m3 = 39; S.a.m3 = [];
  for (var i = 0; i < 40; i++) S.a.m3[i] = 0;
  APP.go('quiz');
  var obs = new MutationObserver(function (recs) { window.__muts += recs.length; });
  obs.observe(document.body, { childList: true, subtree: true });
  var btn = document.getElementById('next');
  btn.click();
  setTimeout(function () {
   var sheet = document.querySelector('.sheet');
   document.title = 'F:SCREEN:' + (S.screen || '?') + ':MUTS:' + window.__muts +
     ':FETCH:' + window.__fetches + ':ERR:' + window.__errs.join(';') +
     ':SHEET:' + (sheet ? sheet.innerHTML.length : 0);
  }, 1500);
 } catch (e) { document.title = 'F:CAUGHT:' + e.message; }
}, 700); });
</script>
"""


def flow_check(html, fails):
    """流程门：**交卷到完成页不能卡死、只能提交一次**（2026-10-25 加）。

    真实候选人反馈「走到第三项最后一题后网页卡住」：
    云版完成页的运行时用 MutationObserver 盯着 body，而 paint() 每次都重写 innerHTML
    ⇒ 改动又触发观察者 ⇒ paint() 又跑 ⇒ **无限渲染循环**，页面直接卡死
    （作答其实已经落库了，只是界面挂了）。
    ⇒ 这里跑一遍真实的「最后一题 → 交卷」：数 DOM 改动次数（> 50 就是死循环）
    与提交次数（必须 ≤ 1：app.js 与云版运行时曾各提交一次，抢同一行）。
    """
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html.rsplit("</body>", 1)[0] + FLOW_JS + "</body></html>")
        tmp = f.name
    try:
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=20000",
                              "--dump-dom", "file://" + tmp],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=45).stdout.decode("utf-8", "ignore")
    except subprocess.TimeoutExpired:
        # 页面挂死时浏览器永远不吐 DOM ⇒ 这本身就是最直接的证据
        fails.append("[流程] 交卷后页面挂死（浏览器一直不返回 DOM）—— 无限渲染循环的特征")
        return
    finally:
        os.unlink(tmp)
    m = re.search(r"<title>([^<]*)</title>", dom)
    title = (m.group(1) if m else "").replace("&gt;", ">")
    mm = re.search(r"F:SCREEN:(\w*):MUTS:(\d+):FETCH:(\d+):ERR:(.*):SHEET:(\d+)", title)
    if not mm:
        fails.append("[流程] 交卷流程自检没跑起来（%s）" % (title or "无回读"))
        return
    screen, muts, fetches = mm.group(1), int(mm.group(2)), int(mm.group(3))
    errs, sheet_len = mm.group(4), int(mm.group(5))
    if screen != "done":
        fails.append("[流程] 交卷后没到完成页（screen=%s）" % screen)
    if muts > 50:
        fails.append("[流程] 完成页在无限重绘（DOM 改动 %d 次）—— 页面会卡死" % muts)
    if fetches > 1:
        fails.append("[流程] 一次交卷发了 %d 次请求 —— 会写重行" % fetches)
    if errs.strip():
        fails.append("[流程] 交卷过程有报错：%s" % errs[:160])
    if screen == "done" and muts <= 50 and fetches <= 1 and not errs.strip():
        print("  交卷流程：到达完成页、DOM 改动 %d 次、提交 %d 次、无报错 ✓" % (muts, fetches))

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    source_only = "--source-only" in sys.argv
    fails = []
    if not source_only:
        path = args[0] if args else DEFAULT_PRODUCT
        if not path.startswith("http") and not os.path.exists(path):
            print("找不到产物：%s" % path)
            return 2
        print("== 成品侧（候选人实际看到的那份）==")
        print("产物：%s" % path)
        html = read_html(path)
        data = extract_data(html)
        check(data, "成品", fails)
        render_check(html, fails)
        flow_check(html, fails)
    print("\n== 题库源文件侧 ==")
    audit_source(fails)
    print("\n==== %s ====" % ("全部通过" if not fails else "有 %d 项未通过" % len(fails)))
    for f in fails:
        print("  - %s" % f)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
