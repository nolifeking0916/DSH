#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""限时口径门（票 #25）：承诺与实现逐句对得上 · 到点真的会自动交卷 · 结果不落用时字段。

这张门守的是三件事：
  1. **承诺 ↔ 实现**：成品里只要出现「自动交卷」这类对外承诺，就必须同时存在
     计时器实现（setInterval + 题头倒计时 + 截止时刻）与告知页的截断规则；
     反过来，实现被删掉时承诺也必须跟着删 —— 两者不得单独存在。
  2. **到点真的会交卷**：headless 实跑，把截止时刻设成 1.5 秒后，页面必须自己
     跳到完成页、留下截断标记（未答 N 题），且施测人报告顶部必须显示该标记。
  3. **结果不落用时字段**：结果 JSON 的字段白名单是
     tool / version / code / name / idLast4 / date / m1 / m2 / m3（+ 截断标记 limitCut），
     任何时长类字段都不许出现（维护者裁定：不把用时落进产品）。

用法：python3 src/verify_limit.py [成品路径]
退出码 0 = 全绿；非 0 = 有项未通过（逐条打印）。
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, "dist", "云上文旅集团核心人才系列测试_20261024.html")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("  [OK ] " if ok else "[FAIL] ") + name + (("：" + detail) if detail else ""))


def run_chrome(js=""):
    """跑一次 headless Chrome（虚拟时间加速定时器），返回渲染后的 DOM。"""
    src = open(PROD, encoding="utf-8").read()
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write((src.rsplit("</body>", 1)[0] + js + "</body></html>") if js else src)
        tmp = f.name
    try:
        out = subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=8000",
             "--dump-dom", "file://" + tmp],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120).stdout.decode("utf-8", "ignore")
    finally:
        os.unlink(tmp)
    return out


def main():
    if not os.path.exists(PROD):
        print("找不到成品：", PROD)
        return 2
    html = open(PROD, encoding="utf-8").read()

    print("== 1. 承诺 ↔ 实现（静态） ==")
    promise = "自动交卷" in html
    check("成品含「自动交卷」承诺", promise, "无承诺则本节其余项自动跳过")
    if promise:
        check("承诺有计时器实现（setInterval）", "setInterval" in html, "")
        check("承诺有题头倒计时元素（t-left）", "t-left" in html, "")
        check("承诺有截止时刻状态（deadline）", "deadline" in html, "")
        check("告知页写明截断规则（限时与交卷说明）", "限时与交卷说明" in html, "")
        check("告知页写明未答怎么处理（未作答）", "未作答" in html, "")
        check("告知页写明起算点（同意并开始测试）", "同意并开始测试" in html, "")
        check("告知页写明续答继续计时", "继续走" in html, "")
    check("限时总时长是一个钟（90 分钟）", re.search(r"LIMIT_MIN\s*=\s*90", html) is not None, "")
    check("起算点是「同意并开始测试」（不是进页面）",
          re.search(r"if\s*\(\s*S\.limit\s*&&\s*!S\.deadline\s*\)\s*S\.deadline\s*=", html) is not None, "")

    print("\n== 2. 结果 JSON 字段（不落用时字段） ==")
    m = re.search(r"const\s+out\s*=\s*\{(.*?)\}\s*;", html, re.S)
    obj = m.group(1) if m else ""
    keys = re.findall(r"(\w+)\s*:", obj)
    allowed = {"tool", "version", "code", "name", "idLast4", "date", "m1", "m2", "m3"}
    extra = [k for k in keys if k not in allowed]
    check("结果对象字段在白名单内", not extra, "字段：%s" % ",".join(keys))
    check("截断标记随结果导出（限被截断时才带）", re.search(r"out\.limitCut\s*=", html) is not None, "")
    for w in ["duration", "elapsed", "startedAt", "finishedAt", "usedTime", "timeSpent", "用时"]:
        hit = re.search(r"\b%s\b" % w, obj)
        check("结果对象不含「%s」" % w, hit is None, "")

    print("\n== 3. 不限时模式不挂钟（headless） ==")
    js_nolimit = """
<script>window.addEventListener('load',function(){setTimeout(function(){
  try{
    var S=APP.S(); S.name='测试'; S.idLast4='4821'; S.consented=true; S.limit=false;
    APP.save(); APP.go('quiz');
    document.title='T:'+(document.getElementById('t-left')?'has-timer':'no-timer');
  }catch(e){document.title='ERR:'+e.message;}
},200);});</script>
"""
    dom = run_chrome(js_nolimit)
    tm = re.search(r"<title>([^<]*)</title>", dom)
    check("不限时模式答题页没有倒计时", (tm.group(1) if tm else "").endswith("no-timer"),
          tm.group(1) if tm else "")

    print("\n== 4. 到点自动交卷 + 截断标记（headless） ==")
    js_cut = """
<script>window.addEventListener('load',function(){setTimeout(function(){
  try{
    var S=APP.S(); S.name='测试'; S.idLast4='4821'; S.consented=true; S.limit=true;
    S.a.m1[0]=0; S.a.m1[1]=1;          // 只答 2 题，其余全未答
    S.deadline=Date.now()+1500;        // 截止时刻定在 1.5 秒后
    APP.save(); APP.go('quiz');
    setTimeout(function(){
      var S2=APP.S();
      var cut=S2.limitCut?JSON.stringify(S2.limitCut):'none';
      var body=document.body.innerText||'';
      document.title='CUT:'+cut+':screen:'+(body.indexOf('已自动交卷')>=0?'ok':'bad');
    },4000);
  }catch(e){document.title='ERR:'+e.message;}
},200);});</script>
"""
    dom = run_chrome(js_cut)
    tm = re.search(r"<title>([^<]*)</title>", dom)
    title = tm.group(1) if tm else ""
    check("到点后页面自动交卷（跳到完成页并写明已自动交卷）", "screen:ok" in title, title)
    m2 = re.search(r"CUT:(\{.*?\}|none):", title)
    cut = m2.group(1) if m2 else ""
    check("截断标记写进状态", cut not in ("", "none"), cut)
    if cut not in ("", "none"):
        try:
            c = json.loads(cut)
            check("截断标记带未答题数", isinstance(c.get("unanswered"), int) and c["unanswered"] > 0, cut)
            check("未答题数与实际一致（m1 答 2 题 → 未答 94）", c.get("m1") == 94, cut)
        except Exception as e:  # noqa: BLE001
            check("截断标记可解析", False, "%s：%s" % (cut, e))

    print("\n== 5. 施测人侧看得见截断标记（headless） ==")
    js_rep = """
<script>window.addEventListener('load',function(){setTimeout(function(){
  try{
    var S=APP.S(); S.name='测试'; S.idLast4='4821'; S.consented=true; S.limit=true;
    S.a.m1[0]=0; S.a.m1[1]=1;
    S.deadline=Date.now()+1500;
    APP.save(); APP.go('quiz');
    setTimeout(function(){
      APP.openReport();
      setTimeout(function(){
        var body=document.body.innerText||'';
        document.title='REP:'+(body.indexOf('限时到点自动交卷')>=0?'ok':'bad');
      },800);
    },4000);
  }catch(e){document.title='ERR:'+e.message;}
},200);});</script>
"""
    dom = run_chrome(js_rep)
    tm = re.search(r"<title>([^<]*)</title>", dom)
    check("施测人报告里能看到「限时到点自动交卷」", (tm.group(1) if tm else "").endswith("REP:ok"),
          tm.group(1) if tm else "")

    print("\n== 6. 告知页的限时说明（勾了限时才出现） ==")
    js_consent = """
<script>window.addEventListener('load',function(){setTimeout(function(){
  try{
    var S=APP.S(); S.name='测试'; S.idLast4='4821'; S.limit=true; APP.save();
    APP.go('consent');
    var body=document.body.innerText||'';
    document.title='C:'+(body.indexOf('限时与交卷说明')>=0?'ok':'bad');
  }catch(e){document.title='ERR:'+e.message;}
},200);});</script>
"""
    dom = run_chrome(js_consent)
    tm = re.search(r"<title>([^<]*)</title>", dom)
    check("勾了限时时告知卡出现「限时与交卷说明」", (tm.group(1) if tm else "").endswith("C:ok"),
          tm.group(1) if tm else "")

    bad = [x for x in results if not x[1]]
    print("\n==== %s ====" % ("全部通过" if not bad else "有 %d 项未通过" % len(bad)))
    for name, _, detail in bad:
        print("  - %s（%s）" % (name, detail))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
