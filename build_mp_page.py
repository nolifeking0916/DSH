# -*- coding: utf-8 -*-
"""生成 MP 序列称职度沟通计划汇报页（142 人，已逐人核对后台，可导出长图）"""
import csv, collections, os

SRC = "/tmp/mp_final.csv"
VER = "/tmp/mp_verify.csv"
H2C = "/tmp/html2canvas.min.js"
OUT = "/Users/leto/Downloads/MP序列称职度沟通计划_汇报页_20261021.html"

data = list(csv.DictReader(open(SRC, encoding="utf-8")))
for d in data:
    d["co"] = d["co"].strip()
    d["name"] = d["name"].strip()
ver = list(csv.DictReader(open(VER, encoding="utf-8")))
vstat = collections.Counter(v["status"] for v in ver)
pending = [v for v in ver if v["status"] not in ("一致", "岗位更新")]

DAYS = [("2026-10-22", "周四"), ("2026-10-23", "周五"), ("2026-10-24", "周六"), ("2026-10-25", "周日")]
GROUPS = [
    ["云上度假村", "云上景区"],
    ["浙江营销", "集团部门", "大竹海"],
    ["茅山森林世界", "研创院", "工程管理分公司"],
    ["余村演艺分公司", "星空酒店", "聚力旅行社", "恐龙酒店", "云上商管", "熊猫部落"],
]

def slots():
    out = []
    for i in range(18):
        t = 540 + i * 10
        out.append(("%02d:%02d" % (t // 60, t % 60), "%02d:%02d" % ((t + 10) // 60, (t + 10) % 60)))
    for i in range(32):
        t = 780 + i * 10
        out.append(("%02d:%02d" % (t // 60, t % 60), "%02d:%02d" % ((t + 10) // 60, (t + 10) % 60)))
    return out

by = collections.OrderedDict()
for d in data:
    by.setdefault(d["co"], []).append(d)
flat = [c for g in GROUPS for c in g]
assert sorted(flat) == sorted(by.keys()), (sorted(flat), sorted(by.keys()))

plan = []
for (day, wd), grp in zip(DAYS, GROUPS):
    ss = slots(); k = 0
    for co in grp:
        for p in by[co]:
            s, e = ss[k]
            plan.append(dict(day=day, wd=wd, start=s, end=e, co=co, p=p))
            k += 1
assert len(plan) == len(data)

def day_stats(day):
    items = [x for x in plan if x["day"] == day]
    orgs = []
    for x in items:
        if not orgs or orgs[-1]["co"] != x["co"]:
            orgs.append({"co": x["co"], "n": 0, "segs": []})
        o = orgs[-1]; o["n"] += 1
        t = int(x["start"][:2]) * 60 + int(x["start"][3:])
        if not o["segs"] or t - o["segs"][-1][1] > 10:
            o["segs"].append([t, t + 10])
        else:
            o["segs"][-1][1] = t + 10
    return orgs

def seg_txt(segs):
    return " / ".join("%02d:%02d–%02d:%02d" % (a // 60, a % 60, b // 60, b % 60) for a, b in segs)

m_n = sum(1 for d in data if d["lv"].startswith("M"))
p_n = sum(1 for d in data if d["lv"].startswith("P"))
org_n = len(by)
hours = round(len(data) * 10 / 60.0, 1)

parts = ["""<div class="cover">
  <div class="cover-tag">集团行政人事部 · 干部与人才盘点</div>
  <h1>MP序列称职度沟通计划</h1>
  <div class="cover-sub">%d 人 · 每人 10 分钟 · 2026 年 10 月 22 日 9:00 起，10 月 25 日前完成</div>
  <div class="kpis">
    <div class="kpi"><b>%d</b><span>评估人数</span></div>
    <div class="kpi"><b>%d</b><span>覆盖机构</span></div>
    <div class="kpi"><b>10</b><span>分钟 / 人</span></div>
    <div class="kpi"><b>%s</b><span>小时总量</span></div>
    <div class="kpi"><b>4</b><span>天完成（含周末）</span></div>
    <div class="kpi"><b>3</b><span>方参会</span></div>
  </div>
  <div class="cover-meta">M 序列 %d 人 ／ P 序列 %d 人 ｜ 每日 9:00–12:00、13:00 起（午休 1 小时），当天排完即止 ｜ 名单已逐人比对系统后台</div>
</div>""" % (len(data), len(data), org_n, hours, m_n, p_n)]

parts.append('<div class="section"><div class="sec-title">一、排期总览</div><div class="days">')
for day, wd in DAYS:
    orgs = day_stats(day)
    tt = sum(o["n"] for o in orgs)
    parts.append('<div class="day"><div class="day-head"><b>%s</b><span>%s · %d 人</span></div>' % (day[5:].replace("-", "/"), wd, tt))
    for o in orgs:
        parts.append('<div class="day-row"><span class="org">%s<em>%d 人</em></span><span class="time">%s</span><span class="way">面对面/线上会议</span></div>'
                     % (o["co"], o["n"], seg_txt(o["segs"])))
    parts.append("</div>")
parts.append("</div></div>")

# 二、名单核对
parts.append("""<div class="section"><div class="sec-title">二、名单与系统后台核对</div>
<div class="verify">
  <div class="vstats">
    <div class="vs"><b>%d</b><span>名单人数</span></div>
    <div class="vs"><b>%d</b><span>岗位与后台一致</span></div>
    <div class="vs"><b>%d</b><span>岗位按后台更新</span></div>
    <div class="vs warn"><b>%d</b><span>待人工确认</span></div>
  </div>
  <div class="vnote">核对基准：企业后台人员主数据 2026-10-21 18:01 同步版本，逐人比对姓名、在职机构、岗位、职级、入职日期；岗位更新项以后台为准，名单原值保留在明细表备注列。</div>
</div>""" % (len(ver), vstat.get("一致", 0), vstat.get("岗位更新", 0), len(pending)))

if pending:
    parts.append('<table class="mini"><thead><tr><th>机构（名单）</th><th>姓名</th><th>名单岗位</th><th>后台在职记录</th><th>处理建议</th></tr></thead><tbody>')
    for v in pending:
        if v["alt"]:
            alt = "同名的在职记录：%s" % v["alt"].replace("；", "；")
        elif v["db_state"] == "离职":
            alt = "仅见同名离职记录（%s / %s）" % (v["db_org"], v["db_pos"])
        else:
            alt = "无同名记录"
        parts.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>沟通前向机构确认现任岗位与机构归属</td></tr>'
                     % (v["co"], v["name"], v["list_pos"], alt))
    parts.append("</tbody></table>")
    parts.append('<div class="legend">以上人员仍保留在名单中，岗位与职级按名单原值列示，未按后台改写；沟通前请与对应机构确认。</div>')
else:
    parts.append('<div class="vall">全部名单人员均已通过核对：姓名、在职机构、岗位、职级、入职日期与企业后台（2026-10-21 18:01 同步）一致，或已按后台更新并留存原值。</div>')

# 三、评估方法与判定口径
parts.append("""</div><div class="section"><div class="sec-title">三、评估方法与判定口径</div>
<div class="rules">
  <div class="rule"><h4>10 分钟结构与分工</h4>
    <p><b>0–1 分　说明目的与边界</b>　仅就岗位胜任度作事实性确认，不涉及薪酬、任免与个人评价。</p>
    <p><b>1–5 分　履职事实陈述</b>　机构负责人、人力资源负责人各 2 分钟，陈述被评估人近半年一项可验证的履职事实，含事项、时间与结果。</p>
    <p><b>5–8 分　结构化追问</b>　按专业技能、管理技能、发展潜力三个维度依次追问，要求以事实与数据作答。</p>
    <p><b>8–10 分　评分与结论</b>　完成三项评分与结论，并以一句事实性表述记录判定依据。</p>
  </div>
  <div class="rule"><h4>评分标准与判定规则</h4>
    <p>三项权重均为 33%，每项 0–5 分：5 分显著超出岗位要求，3 分符合要求，1 分明显不足；加权分为三项算术平均。</p>
    <p class="big"><span class="pill ok">行</span>加权分 ≥ 3.0，且三项均不低于 2.0</p>
    <p class="big"><span class="pill no">不行</span>加权分 &lt; 3.0，或任一项低于 2.0</p>
    <p>结论仅设「行 / 不行」两档；判定依据采用事实与行为证据表述，不使用评价性形容词。</p>
  </div>
  <div class="rule"><h4>参会方职责与方式</h4>
    <p><b>机构负责人</b>　就业务结果与岗位要求的匹配度提供事实，并对是否胜任给出结论。</p>
    <p><b>人力资源负责人</b>　就任职资格、绩效记录、团队反馈与风险点提供依据。</p>
    <p><b>集团相关方</b>　我、汪洋、陈信克，负责主持、追问、记录与结论归档。</p>
    <p>面谈方式统一为<b>面对面 / 线上会议</b>：同城机构安排面对面，异地机构安排线上会议。</p>
  </div>
</div></div>""")

# 四、名单
parts.append('<div class="section"><div class="sec-title">四、逐人沟通安排（%d 人）</div><table class="list"><thead><tr>'
             '<th class="c-idx">#</th><th class="c-time">日期</th><th class="c-time">时间</th><th class="c-org">机构</th>'
             '<th class="c-name">姓名</th><th class="c-pos">岗位</th><th class="c-lv">职级</th><th class="c-date">入职日期</th>'
             '<th class="c-way">方式</th><th class="c-note">核对备注</th>'
             '</tr></thead><tbody>' % len(plan))
cur = None
for i, x in enumerate(plan, 1):
    if x["co"] != cur:
        cur = x["co"]
        parts.append('<tr class="grp"><td colspan="10"><span class="g-org">%s</span>'
                     '<span class="g-people">机构负责人　｜　人力资源负责人　｜　集团相关方：我、汪洋、陈信克</span>'
                     '<span class="g-way">面对面/线上会议</span></td></tr>' % cur)
    note = x["p"].get("note2", "") or ""
    parts.append('<tr><td class="c-idx">%d</td><td>%s</td><td>%s</td><td class="c-org">%s</td><td class="c-name">%s</td>'
                 '<td class="c-pos">%s</td><td class="c-lv">%s</td><td class="c-date">%s</td><td class="c-way">面对面/线上会议</td>'
                 '<td class="c-note">%s</td></tr>'
                 % (i, x["day"][5:].replace("-", "/"), x["start"], x["co"], x["p"]["name"],
                    x["p"]["pos"], x["p"]["lv"], x["p"].get("entry", ""), note))
parts.append("</tbody></table>")
parts.append('<div class="legend">岗位与职级取自企业后台 2026-10-21 18:01 同步数据；入职日期为后台入职日期。'
             '标注「岗位按后台更新」的行，括号内为名单原值，供追溯。</div>')
parts.append("</div>")
parts.append('<div class="footer">制表：集团行政人事部　｜　2026-10-21　｜　共 %d 人 · %d 家机构 · 每人 10 分钟 · 结果口径：行 / 不行　｜　数据来源：企业后台人员主数据（同步时间 2026-10-21 18:01）</div>' % (len(plan), org_n))
body = "\n".join(parts)

h2c = open(H2C, encoding="utf-8").read()

html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>MP序列称职度沟通计划</title>
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
.days{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;align-items:start}
.day{border:1px solid #DDE3DA;border-radius:10px;overflow:hidden}
.day-head{background:#F5F0E4;padding:10px 12px;display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid #E4DCC8}
.day-head b{font-size:15px;color:#1E4634}
.day-head span{font-size:11px;color:#6B7268}
.day-row{padding:7px 12px;border-bottom:1px dashed #E8ECE5;font-size:12px;display:flex;flex-wrap:wrap;gap:4px 6px}
.day-row:last-child{border-bottom:0}
.day-row .org{font-weight:600;color:#2C4A3A;flex:1 1 100%}
.day-row .org em{font-style:normal;font-weight:400;color:#8A9287;font-size:11px;margin-left:6px}
.day-row .time{color:#4A544A;font-size:11px}
.day-row .way{margin-left:auto;font-size:10px;color:#1E4634;background:#EDF2EE;border-radius:3px;padding:1px 6px}
.verify{display:flex;gap:26px;align-items:stretch;border:1px solid #E7E1CE;background:#FBF9F3;border-radius:10px;padding:18px 20px;margin-bottom:14px}
.vstats{display:grid;grid-template-columns:repeat(4,96px);gap:10px;flex:0 0 auto}
.vs{border:1px solid #E4DCC8;background:#fff;border-radius:8px;padding:10px 6px;text-align:center}
.vs b{display:block;font-size:23px;color:#1E4634}
.vs span{display:block;font-size:10.5px;color:#6B7268;margin-top:4px}
.vs.warn b{color:#A5443A}
.vnote{font-size:12px;line-height:1.85;color:#4A544A;align-self:center}
.vnote b{color:#1E4634}
table.mini{width:100%;border-collapse:collapse;font-size:11.5px;margin-top:4px}
table.mini th{background:#EDF2EE;color:#1E4634;font-weight:600;padding:7px 8px;text-align:left;border-bottom:1px solid #DCE4DA}
table.mini td{padding:6px 8px;border-bottom:1px solid #EFF1EC;color:#333}
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
table.list th{background:#1E4634;color:#fff;font-weight:600;padding:9px 6px;text-align:left;font-size:11.5px}
table.list td{padding:6px 6px;border-bottom:1px solid #EDEFE9;color:#2B322B;vertical-align:middle}
table.list tbody tr:nth-child(even) td{background:#FAFBF8}
tr.grp td{background:#F5F0E4 !important;padding:9px 8px;border-top:2px solid #E0D6BC;border-bottom:1px solid #E0D6BC}
tr.grp .g-org{font-weight:700;color:#1E4634;font-size:12.5px;margin-right:12px}
tr.grp .g-people{font-size:11px;color:#6A7267}
tr.grp .g-way{float:right;font-size:10.5px;color:#fff;background:#1E4634;border-radius:3px;padding:1px 7px}
.c-idx{width:42px;text-align:center;color:#8A9287}
.c-time{width:56px;color:#5A635A}
.c-org{width:104px}
.c-name{width:72px;font-weight:600;color:#1E4634}
.c-pos{width:240px}
.c-lv{width:46px;text-align:center;color:#5A635A}
.c-date{width:82px;text-align:center;color:#5A635A}
.c-way{width:112px;text-align:center;color:#5A635A}
.c-note{width:200px;color:#8A6A2F;font-size:10.5px;line-height:1.5}
.legend{font-size:11px;color:#8A9287;margin-top:10px;line-height:1.6}
.vall{font-size:12.2px;color:#2E7D52;background:#EDF5EF;border:1px solid #D5E6DA;border-radius:8px;padding:11px 14px;margin:2px 0 6px}
.footer{margin-top:24px;padding:18px 56px 34px;font-size:11.5px;color:#8A9287;border-top:1px solid #EDEFE9}
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
      a.download='MP序列称职度沟通计划_长图_'+s+'.png';
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
print("saved", OUT, os.path.getsize(OUT), "rows", len(plan), "orgs", org_n, "pending", len(pending))
