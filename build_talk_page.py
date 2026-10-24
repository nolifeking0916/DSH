# -*- coding: utf-8 -*-
"""MP序列称职度沟通计划（125 人）汇报页：单文件 HTML + 一键长图"""
import json, collections, os

PLAN = "/tmp/talk_plan.json"
H2C = "/tmp/html2canvas.min.js"
OUT = "/Users/leto/Downloads/MP序列称职度沟通计划_125人_汇报页_20261022.html"

plan = json.load(open(PLAN, encoding="utf-8"))
REMOVED = [("王继月", "大竹海", "总经理", "机构一把手"),
           ("赵剑平", "工程管理分公司", "总经理", "机构一把手"),
           ("肖毅", "云上度假村", "储备总经理", "一把手序列（储备总经理）"),
           ("章娅君", "大竹海", "副总经理", "机构班子成员"),
           ("李学飞", "云上景区", "行政人事总监", "人力负责人，本轮为陪谈方")]

by_day = collections.OrderedDict()
for x in plan:
    by_day.setdefault((x["day"], x["wd"]), []).append(x)
org_n = len({x["co"] for x in plan})
hours = round(len(plan) * 10 / 60.0, 1)

def day_orgs(items):
    out = []
    for x in items:
        if not out or out[-1]["co"] != x["co"]:
            out.append({"co": x["co"], "n": 0, "s": x["s"], "e": x["e"]})
        o = out[-1]; o["n"] += 1; o["e"] = x["e"]
    return out

parts = ["""<div class="cover">
  <div class="cover-tag">集团行政人事部 · 干部与人才盘点</div>
  <h1>MP序列称职度沟通计划</h1>
  <div class="cover-sub">125 人 · 每人 10 分钟 · 2026 年 10 月 22 日 13:00 起 · 4 天完成</div>
  <div class="kpis">
    <div class="kpi"><b>130</b><span>原计划应谈</span></div>
    <div class="kpi"><b>125</b><span>本次实谈</span></div>
    <div class="kpi"><b>%d</b><span>覆盖机构</span></div>
    <div class="kpi"><b>10</b><span>分钟 / 人</span></div>
    <div class="kpi"><b>%s</b><span>小时总量</span></div>
    <div class="kpi"><b>4</b><span>天完成</span></div>
  </div>
  <div class="cover-meta">剔除一把手、班子成员与陪谈的人力负责人共 5 人 ｜ 每日按机构成块排期 ｜ 午休 1 小时 ｜ 面谈方式：面对面 / 线上会议</div>
</div>""" % (org_n, hours)]

parts.append("""<div class="section"><div class="sec-title">一、人数口径：应谈与实谈</div>
<div class="verify">
  <div class="vstats">
    <div class="vs"><b>130</b><span>原计划应谈</span></div>
    <div class="vs"><b>125</b><span>本次实谈</span></div>
    <div class="vs warn"><b>−5</b><span>差额</span></div>
    <div class="vs"><b>%d</b><span>覆盖机构</span></div>
  </div>
  <div class="vnote">剔除口径：机构一把手、机构班子成员、本轮承担逐人陪谈的人力资源负责人，以及近期刚发生职位变动的人员，暂不作为被评估对象。</div>
</div>""" % org_n)

parts.append('<table class="mini"><thead><tr><th>姓名</th><th>机构</th><th>岗位</th><th>剔除原因</th></tr></thead><tbody>')
for nm, co, pos, why in REMOVED:
    parts.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (nm, co, pos, why))
parts.append('</tbody></table><div class="legend">以上 5 人不在本次被评估名单内；其中一把手 3 人、班子成员 1 人、人力负责人 1 人。</div></div>')

parts.append('<div class="section"><div class="sec-title">二、排期总览（4 天 · %d 人）</div><div class="days">' % len(plan))
for (day, wd), items in by_day.items():
    orgs = day_orgs(items)
    parts.append('<div class="day"><div class="day-head"><b>%s %s</b><span>%d 人 · %s–%s</span></div>'
                 % (day[5:].replace("-", "/"), wd, len(items), items[0]["s"], items[-1]["e"]))
    for o in orgs:
        parts.append('<div class="day-row"><span class="org">%s<em>%d 人</em></span><span class="time">%s–%s</span></div>'
                     % (o["co"], o["n"], o["s"], o["e"]))
    parts.append("</div>")
parts.append("</div>")
parts.append('<div class="legend">合计 %d 人 / %s 小时（净）。今日 13:00 起；10/23–24 为 9:00 起并含 12:00–13:00 午休；10/25 仅上午。同一机构不跨天，减少换场。</div></div>' % (len(plan), hours))

parts.append("""<div class="section"><div class="sec-title">三、结构化面谈评估方式</div>
<div class="rules">
  <div class="rule"><h4>10 分钟结构与分工</h4>
    <p><b>0–1 分</b>　说明目的与边界：仅就岗位胜任度作事实性确认，不涉及薪酬、任免与个人评价。</p>
    <p><b>1–5 分</b>　机构负责人、人力资源负责人各 2 分钟，陈述一项可验证的履职事实（事项、时间、结果）。</p>
    <p><b>5–8 分</b>　按专业技能、管理技能、发展潜力三维度依次追问，要求以事实与数据作答。</p>
    <p><b>8–10 分</b>　完成评分与结论，并以一句事实性表述记录判定依据。</p>
  </div>
  <div class="rule"><h4>评分标准与判定规则</h4>
    <p>三项权重均 33%，每项 0–5 分：5 分显著超出、3 分符合、1 分明显不足；加权分为三项算术平均。</p>
    <p class="big"><span class="pill ok">行</span>加权分 ≥ 3.0，且三项均不低于 2.0</p>
    <p class="big"><span class="pill no">不行</span>加权分 &lt; 3.0，或任一项低于 2.0</p>
    <p>结论仅设两档；判定依据用事实与行为证据表述，不使用评价性形容词。</p>
  </div>
  <div class="rule"><h4>参会方与职责</h4>
    <p><b>机构负责人</b>　就业务结果与岗位要求的匹配度提供事实，并对是否胜任给出结论。</p>
    <p><b>人力资源负责人</b>　就任职资格、绩效记录、团队反馈与风险点提供依据。</p>
    <p><b>集团相关方</b>　我、汪洋、陈信克，负责主持、追问、记录与结论归档。</p>
    <p>方式统一为<b>面对面 / 线上会议</b>；结论当日归档，按机构汇总。</p>
  </div>
</div></div>""")

parts.append('<div class="section"><div class="sec-title">四、人员清单（%d 人）</div><table class="list"><thead><tr>'
             '<th class="c-idx">#</th><th class="c-name">姓名</th><th class="c-sex">性别</th><th class="c-num">年龄</th>'
             '<th class="c-ten">司龄</th><th class="c-edu">学历</th><th class="c-pos">岗位</th><th class="c-lv">职级</th>'
             '<th class="c-pay">月薪（元）</th></tr></thead><tbody>' % len(plan))
cur = None
for i, x in enumerate(plan, 1):
    if x["co"] != cur:
        cur = x["co"]
        n = sum(1 for y in plan if y["co"] == cur)
        parts.append('<tr class="grp"><td colspan="9"><span class="g-org">%s</span><span class="g-n">%d 人</span></td></tr>' % (cur, n))
    parts.append('<tr><td class="c-idx">%d</td><td class="c-name">%s</td><td class="c-sex">%s</td><td class="c-num">%s</td>'
                 '<td class="c-ten">%s</td><td class="c-edu">%s</td><td class="c-pos">%s</td><td class="c-lv">%s</td>'
                 '<td class="c-pay">%s</td></tr>'
                 % (i, x["name"], x["sex"], x["age"], x["tenure"], x["degree"] or "—", x["pos"], x["lv"], x["pay"] or "待补"))
parts.append("</tbody></table>")
parts.append('<div class="legend">年龄按 2026-10-22 计算，司龄为入职至今日；月薪为职位定级月薪（不含五险一金与年终奖），'
             '优先取四定统览表，其余取薪资标准表 2026-09；3 名新入职尚未出薪标注「待补」。</div>')
parts.append("</div>")
parts.append('<div class="footer">制表：集团行政人事部　｜　2026-10-22　｜　共 %d 人 · %d 家机构 · 每人 10 分钟 · 结果口径：行 / 不行　｜　'
             '数据来源：企业后台人员主数据（2026-10-21 18:01 同步版）、各机构四定统览表（202602）、薪资标准表（2026-09）</div>' % (len(plan), org_n))
body = "\n".join(parts)

h2c = open(H2C, encoding="utf-8").read()
html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>MP序列称职度沟通计划（125人）</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#E7E9E4;font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;color:#222;padding:28px 0 60px}
#page{width:1240px;margin:0 auto;background:#fff;box-shadow:0 10px 40px rgba(0,0,0,.12)}
.cover{background:linear-gradient(135deg,#1E4634 0%,#2E5B46 60%,#3A6B53 100%);color:#fff;padding:54px 56px 44px;position:relative}
.cover:after{content:"";position:absolute;right:-60px;top:-60px;width:300px;height:300px;border-radius:50%;background:rgba(245,240,228,.06)}
.cover-tag{font-size:13px;letter-spacing:2px;color:#D9C79A;margin-bottom:18px}
.cover h1{font-size:44px;font-weight:700;letter-spacing:2px;margin-bottom:14px}
.cover-sub{font-size:16px;color:#E9E4D6;margin-bottom:34px}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:14px;margin-bottom:26px}
.kpi{background:rgba(255,255,255,.09);border:1px solid rgba(245,240,228,.22);border-radius:10px;padding:16px 10px;text-align:center}
.kpi b{display:block;font-size:32px;color:#F5F0E4;line-height:1.1}
.kpi span{display:block;font-size:12px;color:#CFD8CD;margin-top:6px}
.cover-meta{font-size:12.5px;color:#C9D3C7;border-top:1px solid rgba(255,255,255,.16);padding-top:16px;line-height:1.7}
.section{padding:32px 56px 10px}
.sec-title{font-size:21px;font-weight:700;color:#1E4634;border-left:6px solid #C8A96A;padding-left:12px;margin-bottom:20px}
.verify{display:flex;gap:26px;align-items:stretch;border:1px solid #E7E1CE;background:#FBF9F3;border-radius:10px;padding:18px 20px;margin-bottom:14px}
.vstats{display:grid;grid-template-columns:repeat(4,96px);gap:10px;flex:0 0 auto}
.vs{border:1px solid #E4DCC8;background:#fff;border-radius:8px;padding:10px 6px;text-align:center}
.vs b{display:block;font-size:23px;color:#1E4634}
.vs span{display:block;font-size:10.5px;color:#6B7268;margin-top:4px}
.vs.warn b{color:#A5443A}
.vnote{font-size:12.5px;line-height:1.9;color:#4A544A;align-self:center}
table.mini{width:100%;border-collapse:collapse;font-size:12px;margin-top:4px}
table.mini th{background:#EDF2EE;color:#1E4634;font-weight:600;padding:8px 10px;text-align:left;border-bottom:1px solid #DCE4DA}
table.mini td{padding:7px 10px;border-bottom:1px solid #EFF1EC;color:#333}
.days{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;align-items:start}
.day{border:1px solid #DDE3DA;border-radius:10px;overflow:hidden}
.day-head{background:#F5F0E4;padding:10px 12px;display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid #E4DCC8;flex-wrap:wrap;gap:4px}
.day-head b{font-size:14.5px;color:#1E4634}
.day-head span{font-size:10.5px;color:#6B7268}
.day-row{padding:7px 12px;border-bottom:1px dashed #E8ECE5;font-size:12px;display:flex;gap:6px;align-items:baseline}
.day-row:last-child{border-bottom:0}
.day-row .org{font-weight:600;color:#2C4A3A;flex:1}
.day-row .org em{font-style:normal;font-weight:400;color:#8A9287;font-size:11px;margin-left:6px}
.day-row .time{color:#4A544A;font-size:11px;white-space:nowrap}
.rules{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.rule{background:#FBF9F3;border:1px solid #E7E1CE;border-radius:10px;padding:16px 16px 12px}
.rule h4{font-size:13.5px;color:#1E4634;margin-bottom:10px;padding-bottom:8px;border-bottom:1px dashed #DCD3B8}
.rule p{font-size:12.2px;line-height:1.8;color:#3D453B;margin-bottom:7px}
.rule b{color:#1E4634}
.rule .big{display:flex;align-items:center;gap:8px;font-size:12.6px;color:#2C4A3A;font-weight:600}
.pill{display:inline-block;min-width:44px;text-align:center;border-radius:4px;padding:2px 8px;font-size:12px;color:#fff}
.pill.ok{background:#2E7D52}
.pill.no{background:#A5443A}
table.list{width:100%;border-collapse:collapse;font-size:12px}
table.list th{background:#1E4634;color:#fff;font-weight:600;padding:9px 8px;text-align:left;font-size:11.5px}
table.list td{padding:6px 8px;border-bottom:1px solid #EDEFE9;color:#2B322B}
table.list tbody tr:nth-child(even) td{background:#FAFBF8}
tr.grp td{background:#F5F0E4 !important;padding:8px 10px;border-top:2px solid #E0D6BC;border-bottom:1px solid #E0D6BC}
tr.grp .g-org{font-weight:700;color:#1E4634;font-size:12.5px;margin-right:10px}
tr.grp .g-n{font-size:11px;color:#6A7267}
.c-idx{width:40px;text-align:center;color:#8A9287}
.c-name{width:78px;font-weight:600;color:#1E4634}
.c-sex{width:44px;text-align:center}
.c-num{width:48px;text-align:center}
.c-ten{width:96px;text-align:center;color:#5A635A}
.c-edu{width:56px;text-align:center;color:#5A635A}
.c-pos{width:260px}
.c-lv{width:52px;text-align:center;color:#5A635A}
.c-pay{width:96px;text-align:right;color:#1E4634;font-weight:600;padding-right:14px}
.legend{font-size:11px;color:#8A9287;margin-top:10px;line-height:1.7}
.footer{margin-top:24px;padding:18px 56px 34px;font-size:11.5px;color:#8A9287;border-top:1px solid #EDEFE9;line-height:1.7}
#bar{position:fixed;right:26px;top:24px;display:flex;gap:10px;z-index:99}
#bar button{border:0;border-radius:8px;padding:11px 18px;font-size:13px;font-family:inherit;cursor:pointer;background:#1E4634;color:#fff;box-shadow:0 4px 14px rgba(30,70,52,.28)}
#bar button.ghost{background:#fff;color:#1E4634;border:1px solid #C9D3C7;box-shadow:none}
#bar button:disabled{opacity:.6;cursor:wait}
#tip{position:fixed;left:50%;top:24px;transform:translateX(-50%);background:#1E4634;color:#fff;font-size:12.5px;padding:9px 16px;border-radius:8px;opacity:0;transition:.25s;z-index:100;pointer-events:none}
#tip.on{opacity:1}
@media print{body{background:#fff;padding:0}#page{box-shadow:none;width:100%}#bar,#tip{display:none}tr.grp{page-break-inside:avoid}}
</style></head>
<body>
<div id="bar">
  <button id="btn-png">导出长图</button>
  <button id="btn-print" class="ghost">打印 / PDF</button>
</div>
<div id="tip"></div>
<div id="page">
BODY
</div>
<script>H2C</script>
<script>
(function(){
  var tip=document.getElementById('tip');
  function toast(t){tip.textContent=t;tip.classList.add('on');setTimeout(function(){tip.classList.remove('on')},1800)}
  var btn=document.getElementById('btn-png');
  btn.onclick=async function(){
    if(!window.html2canvas){toast('导出组件未加载');return}
    var page=document.getElementById('page'), label=btn.textContent;
    btn.disabled=true; btn.textContent='生成中…';
    try{
      await new Promise(function(r){setTimeout(r,80)});
      var canvas=await html2canvas(page,{scale:2,backgroundColor:'#ffffff',useCORS:true});
      var a=document.createElement('a'), d=new Date();
      var s=d.getFullYear()+String(d.getMonth()+1).padStart(2,'0')+String(d.getDate()).padStart(2,'0');
      a.download='MP序列称职度沟通计划_125人_长图_'+s+'.png';
      a.href=canvas.toDataURL('image/png'); a.click();
      toast('长图已导出：'+canvas.width+'×'+canvas.height);
    }catch(e){toast('导出失败：'+e.message)}
    btn.disabled=false; btn.textContent=label;
  };
  document.getElementById('btn-print').onclick=function(){window.print()};
})();
</script>
</body></html>"""
html = html.replace("BODY", body).replace("H2C", h2c)
open(OUT, "w", encoding="utf-8").write(html)
print("saved", OUT, os.path.getsize(OUT), "rows", len(plan))
