#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""限时口径门（票 #25 立项 + 票 #39 修订）：承诺与实现逐句对得上 · **到点只提示、不自动交卷** · 结果不落用时字段。

这张门守的是五件事：
  1. **承诺 ↔ 实现**：成品里凡出现「自动交卷」这个词，都必须出现在**否定语境**里
     （到点不会自动交卷）；反过来，实现里不许再藏着一条「到点自动交卷」的路径 ——
     到点处理函数里不许再出现跳完成页的代码。
  2. **到点只提示、不自动交卷**（票 #39 · D3 · 维护者 2026-10-25 12:34 裁定）：
     headless 实跑，把截止时刻设成 1.5 秒后，页面必须**留在答题屏**、给出一次提示、
     剩下的题仍然能作答；到点这一刻的痕迹（已答题数 / 总题数）记进状态。
  3. **手动交卷的结果里带着到点痕迹**：候选人自己把卷答完并交卷后，结果 JSON 里有
     limitHint（{answered, total}）；旧字段 limitCut（语义含混的「被截断」）不得复活。
  4. **结果不落用时字段**：结果 JSON 的字段白名单是
     tool / version / code / name / idLast4 / date / m1 / m2 / m3（+ 到点痕迹 limitHint），
     任何时长类字段都不许出现（维护者裁定：不把用时落进产品）。
  5. **报告页口径说明块与五级梯**（票 #39 · D2，附在本题上）：四个报告块都要有
     「口径说明」块（校准前明写尚未校准），总报告 / 第一项 / 第二项要有五级梯。
     —— 这两条本属 report 侧，verify_product.py 由维护者掌握，故并在本门里兜住。

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


def title_of(dom):
    tm = re.search(r"<title>([^<]*)</title>", dom)
    return tm.group(1) if tm else ""


def main():
    if not os.path.exists(PROD):
        print("找不到成品：", PROD)
        return 2
    html = open(PROD, encoding="utf-8").read()

    print("== 1. 承诺 ↔ 实现（静态 · 票 #39 D3：到点不自动交卷） ==")
    hits = re.findall(r"[^。；\n]{0,30}自动交卷", html)
    neg = [h for h in hits if re.search(r"(不|未|没|无|非)[^。；\n]{0,6}自动交卷", h)]
    check("「自动交卷」只出现在否定语境（到点不会自动交卷）",
          len(hits) > 0 and len(hits) == len(neg),
          "%d 处，其中否定语境 %d 处" % (len(hits), len(neg)))
    check("成品不再出现「到点自动交卷」", "到点自动交卷" not in html, "")
    check("告知页写明到点可继续作答", "可以继续作答" in html or "继续作答" in html, "")
    check("承诺有计时器实现（setInterval）", "setInterval" in html, "")
    check("承诺有题头倒计时元素（t-left）", "t-left" in html, "")
    check("承诺有截止时刻状态（deadline）", "deadline" in html, "")
    check("告知页写明截断规则（限时与交卷说明）", "限时与交卷说明" in html, "")
    check("告知页写明未答怎么处理（未作答）", "未作答" in html, "")
    check("告知页写明起算点（同意并开始测试）", "同意并开始测试" in html, "")
    check("告知页写明续答继续计时（继续走）", "继续走" in html, "")
    check("限时总时长是一个钟（90 分钟）", re.search(r"LIMIT_MIN\s*=\s*90", html) is not None, "")
    check("起算点是「同意并开始测试」（不是进页面）",
          re.search(r"if\s*\(\s*S\.limit\s*&&\s*!S\.deadline\s*\)\s*S\.deadline\s*=", html) is not None, "")
    # 实现里不许再藏着「到点自动交卷」的路径：到点处理函数里不得出现 done（跳完成页）
    m_hit = re.search(r"function\s+onLimitHit\s*\(\s*\)\s*\{(.*?)\n\s{2}\}", html, re.S)
    hit_body = m_hit.group(1) if m_hit else ""
    check("到点处理函数存在（onLimitHit）", bool(hit_body), "")
    if hit_body:
        check("到点处理函数里不再跳完成页（不自动交卷）",
              re.search(r"go\(\s*['\"]done['\"]", hit_body) is None
              and re.search(r"screen\s*=\s*['\"]done['\"]", hit_body) is None, "")
        check("到点处理函数不写任何到点痕迹（复审定稿：只提示、不留痕）",
              re.search(r"S\.(limitHint|limitCut)\s*=", hit_body) is None, "")
        check("到点提示只弹一次（一次性开关 limitTipped）",
              re.search(r"if\s*\(\s*limitTipped\s*\)\s*return", hit_body) is not None, "")

    print("\n== 2. 结果 JSON 字段（不落用时字段） ==")
    m = re.search(r"const\s+out\s*=\s*\{(.*?)\}\s*;", html, re.S)
    obj = m.group(1) if m else ""
    keys = re.findall(r"(\w+)\s*:", obj)
    allowed = {"tool", "version", "code", "name", "idLast4", "date", "m1", "m2", "m3"}
    extra = [k for k in keys if k not in allowed]
    check("结果对象字段在白名单内", not extra, "字段：%s" % ",".join(keys))
    check("结果对象恒为 9 个字段（复审定稿：到点不留痕）",
          sorted(keys) == sorted(allowed), "字段：%s" % ",".join(keys))
    check("到点痕迹不进结果（out.limitHint 不存在）",
          re.search(r"out\.limitHint\s*=", html) is None and "limitHint:" not in obj, "")
    check("旧截断标记 limitCut 已下线（结果对象里不出现）",
          re.search(r"out\.limitCut\s*=", html) is None and "limitCut:" not in obj, "")
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
    check("不限时模式答题页没有倒计时", title_of(dom).endswith("no-timer"), title_of(dom))

    print("\n== 4. 到点只提示、不自动交卷（headless 实跑） ==")
    js_hit = """
<script>window.addEventListener('load',function(){setTimeout(function(){
  try{
    var S=APP.S(); S.name='测试'; S.idLast4='4821'; S.consented=true; S.limit=true;
    S.a.m1[0]=0; S.a.m1[1]=1;          // 到点时只答了 2 题
    S.cur.m1=5;                        // 停在第 6 题（未作答）：到点后还能答
    S.deadline=Date.now()+1500;        // 截止时刻定在 1.5 秒后
    APP.save(); APP.go('quiz');
    setTimeout(function(){
      var S2=APP.S();
      var body=document.body.innerText||'';
      var tip=window.__COPY__.limitHitTip;
      var onDone=(S2.screen==='done')||(body.indexOf('下载结果文件')>=0);
      var tipShown=body.indexOf(tip)>=0;
      var before=Object.keys(S2.a.m1).length;
      var opt=document.querySelectorAll('.opt')[0];
      var picked=false;
      if(opt){ APP.pick(opt); picked=true; }
      var after=Object.keys(APP.S().a.m1).length;
      var hint=S2.limitHint?JSON.stringify(S2.limitHint):'none';
      document.title='HIT:'+(onDone?'done':'notdone')+':tip:'+(tipShown?'ok':'bad')
        +':pick:'+((picked&&after>before)?'ok':'bad')+':hint:'+hint;
    },4000);
  }catch(e){document.title='ERR:'+e.message;}
},200);});</script>
"""
    dom = run_chrome(js_hit)
    title = title_of(dom)
    check("到点后没有自动交卷（仍留在答题屏）", ":notdone:" in title, title)
    check("到点提示出现（limitHitTip）", ":tip:ok" in title, title)
    check("到点后剩余题仍可作答", ":pick:ok" in title, title)
    m2 = re.search(r":hint:(\{.*?\}|none)", title)
    hint = m2.group(1) if m2 else ""
    check("到点后没有写任何到点痕迹（复审定稿：只提示、不留痕）", hint == "none", hint)

    print("\n== 5. 手动交卷的结果里带「到点痕迹」（headless 实跑 + 抓真实下载内容） ==")
    js_submit = """
<script>window.addEventListener('load',function(){setTimeout(function(){
  try{
    var S=APP.S(); S.name='测试'; S.idLast4='4821'; S.consented=true; S.limit=true;
    S.a.m1[0]=0; S.a.m1[1]=1;
    S.deadline=Date.now()+1500;
    APP.save(); APP.go('quiz');
    setTimeout(function(){
      try{
      // 到点之后，候选人自己把卷答完并交卷（手动交卷）
      var D=window.__DATA__;
      for(var i=0;i<D.m1.items.length;i++){ S.a.m1[i]=0; }
      D.eq.self_items.forEach(function(x,ix){ S.a.m2[ix]=4; });
      var off=D.eq.self_items.length;
      D.eq.sjt.forEach(function(q,ix){ S.a.m2[off+ix]=0; });
      D.m3.questions.forEach(function(q,ix){ S.a.m3[ix]=q.answer; });
      S.mod='m3'; S.cur.m3=D.m3.questions.length-1;
      APP.save(); APP.go('quiz'); APP.next();
      var screen=APP.S().screen;
      var doneText=document.body.innerText||'';
      var total=D.m1.items.length+D.eq.self_items.length+D.eq.sjt.length+D.m3.questions.length;
      // 抓真实的下载内容（替掉 Blob 构造器，同步拿到结果 JSON）
      var cap=null; var OrigBlob=window.Blob;
      window.Blob=function(parts,opts){ cap=String(parts[0]); return new OrigBlob(parts,opts); };
      APP.download();
      window.Blob=OrigBlob;
      var o=JSON.parse(cap);
      APP.openReport();
      setTimeout(function(){
        var body=document.body.innerText||'';
        document.title='DL:'+JSON.stringify({screen:screen,total:total,hint:o.limitHint||null,
          hasCut:('limitCut' in o),keys:Object.keys(o),
          done:(doneText.indexOf('已完成')>=0?'ok':'bad')
            +':'+(doneText.indexOf('下载结果文件')>=0?'dl':'no-dl')
            +':'+(doneText.indexOf('回传给施测人')>=0?'send':'no-send')
            +':'+(doneText.indexOf('清除本机数据')>=0?'clr':'no-clr'),
          rep:(body.indexOf('限时到点')>=0?'ok':'bad')});
      },700);
      }catch(e){document.title='E2:'+e.message;}
    },4000);
  }catch(e){document.title='ERR:'+e.message;}
},200);});</script>
"""
    dom = run_chrome(js_submit)
    title = title_of(dom)
    m3 = re.search(r"DL:(\{.*\})", title)
    payload = m3.group(1) if m3 else ""
    check("手动交卷流程仍然可用（走到完成页）", payload.startswith("{"), title)
    if payload:
        try:
            p = json.loads(payload)
            check("手动交卷后的页面是完成页", p.get("screen") == "done", str(p.get("screen")))
            check("结果 JSON 里没有任何到点/截断标记字段（复审定稿）",
                  p.get("hint") is None and p.get("hasCut") is False, str(p.get("keys")))
            allowed = {"tool", "version", "code", "name", "idLast4", "date", "m1", "m2", "m3"}
            extra = [k for k in p.get("keys", []) if k not in allowed]
            check("手动交卷的结果字段仍在白名单内（恒 9 个）", not extra, "字段：%s" % ",".join(p.get("keys", [])))
            check("施测人报告里不再出现「限时到点」痕迹", p.get("rep") == "bad", str(p.get("rep")))
            d = p.get("done") or ""
            check("完成页显示「已完成」（D6）", d.startswith("ok:"), d)
            check("完成页不再有「下载结果文件」入口（D6 删干净）", ":no-dl" in d, d)
            check("完成页不再有「回传给施测人」话术（D6 删干净）", ":no-send" in d, d)
            check("完成页不再有「清除本机」入口（D6 撤除）", ":no-clr" in d, d)
        except Exception as e:  # noqa: BLE001
            check("手动交卷结果可解析", False, "%s：%s" % (payload, e))

    print("\n== 6. 报告页口径说明块与五级梯（票 #39 · D2） ==")
    check("报告页有「口径说明」块", "口径说明" in html, "")
    check("校准前明写「尚未经真人样本校准」", "尚未经真人样本校准" in html, "")
    check("口径说明留了切换点（CALIBRATED 开关 + 两套措辞）",
          re.search(r"const\s+CALIBRATED\s*=\s*(true|false)", html) is not None
          and "calibAbs" in html and "calibRef" in html, "")
    check("五级梯样式在册（.ladder）", ".ladder{" in html, "")
    m_lad = re.search(r"function\s+ladderHTML\s*\([^)]*\)\s*\{(.*?)\n\s{2}\}", html, re.S)
    check("五级梯渲染函数存在（ladderHTML）", m_lad is not None, "")
    check("五级梯五格齐全（顶尖→优秀→良好→合格→待提升）",
          re.search(r"const\s+LADDER\s*=\s*\[\s*\"顶尖\"\s*,\s*\"优秀\"\s*,\s*\"良好\"\s*,\s*\"合格\"\s*,\s*\"待提升\"",
                    html) is not None, "")
    check("总报告有五级梯（综合档）", "ladderBlock(\"综合档\"" in html, "")
    check("第二项仍有整体档五级梯", "ladderBlock(\"整体档\", R.m2.grade)" in html, "")
    check("第一项没有整体档五级梯（ADR-0010）",
          "ladderBlock(\"整体档\", R.m1.grade)" not in html and html.count("ladderBlock(\"整体档\"") == 1,
          "%d 处整体档梯（应只剩第二项那 1 处）" % html.count("ladderBlock(\"整体档\""))
    check("口径说明块只出现在第一项报告块（复审定稿：第二、三项不加）",
          html.count("calibNote()") == 2, "%d 处（1 处定义 + 1 处调用）" % html.count("calibNote()"))
    check("总报告有「口径基础」汇总块", "口径基础" in html and "calibBasis()" in html, "")
    check("口径基础汇总两套措辞都在（校准前 / 校准后）",
          "calibBasisAbs" in html and "calibBasisRef" in html, "")

    print("\n== 7. 告知页的限时说明（勾了限时才出现） ==")
    js_consent = """
<script>window.addEventListener('load',function(){setTimeout(function(){
  try{
    var S=APP.S(); S.name='测试'; S.idLast4='4821'; S.limit=true; APP.save();
    APP.go('consent');
    var body=document.body.innerText||'';
    document.title='C:'+(body.indexOf('限时与交卷说明')>=0?'ok':'bad')
      +':'+(body.indexOf('不会自动交卷')>=0?'neg':'bad');
  }catch(e){document.title='ERR:'+e.message;}
},200);});</script>
"""
    dom = run_chrome(js_consent)
    check("勾了限时时告知卡出现「限时与交卷说明」", title_of(dom).startswith("C:ok"), title_of(dom))
    check("告知卡写明「不会自动交卷」（否定语境）", title_of(dom).endswith(":neg"), title_of(dom))

    bad = [x for x in results if not x[1]]
    print("\n==== %s ====" % ("全部通过" if not bad else "有 %d 项未通过" % len(bad)))
    for name, _, detail in bad:
        print("  - %s（%s）" % (name, detail))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
