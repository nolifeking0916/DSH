# -*- coding: utf-8 -*-
"""MP 序列沟通计划表（142 人，含入职日期与后台最新岗位）"""
import csv, collections
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

GREEN, CREAM, LIGHT = "1E4634", "F5F0E4", "EDF2EE"
FONT = "微软雅黑"
thin = Side(style="thin", color="BFBFBF")
B = Border(left=thin, right=thin, top=thin, bottom=thin)
OUT = "/Users/leto/Downloads/MP序列称职度沟通计划_20261022起.xlsx"

data = list(csv.DictReader(open("/tmp/mp_final.csv", encoding="utf-8")))
for d in data:
    d["co"] = d["co"].strip()

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
        t = 9 * 60 + i * 10
        out.append(("%02d:%02d" % (t // 60, t % 60), "%02d:%02d" % ((t + 10) // 60, (t + 10) % 60)))
    for i in range(32):
        t = 13 * 60 + i * 10
        out.append(("%02d:%02d" % (t // 60, t % 60), "%02d:%02d" % ((t + 10) // 60, (t + 10) % 60)))
    return out

by = collections.OrderedDict()
for d in data:
    by.setdefault(d["co"], []).append(d)

plan = []
for (day, wd), grp in zip(DAYS, GROUPS):
    ss = slots(); k = 0
    for co in grp:
        for p in by[co]:
            s, e = ss[k]
            plan.append(dict(day=day, wd=wd, start=s, end=e, co=co, p=p))
            k += 1
assert len(plan) == len(data)

wb = Workbook()
ws = wb.active
ws.title = "01 沟通计划"
ws.sheet_view.showGridLines = False
hdr = ["序号", "日期", "星期", "开始", "结束", "机构", "机构负责人（参会）", "人力资源负责人（参会）",
       "集团相关方（参会）", "姓名", "岗位", "职级", "入职日期", "方式",
       "专业技能", "管理技能", "发展潜力", "加权分", "结论", "一句话依据", "备注"]
w = [6, 11, 6, 7, 7, 14, 16, 20, 22, 10, 30, 7, 11, 15, 9, 9, 9, 9, 7, 30, 26]
for i, x in enumerate(w, 1):
    ws.column_dimensions[get_column_letter(i)].width = x
ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(hdr))
c = ws["A1"]; c.value = "MP序列称职度沟通计划（%d 人 · 每人 10 分钟 · 2026-10-22 9:00 起 · 10-25 前完成）" % len(plan)
c.font = Font(name=FONT, size=14, bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor=GREEN)
c.alignment = Alignment(horizontal="center", vertical="center"); ws.row_dimensions[1].height = 34

for i, h in enumerate(hdr, 1):
    c = ws.cell(row=2, column=i, value=h)
    c.font = Font(name=FONT, size=9, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=GREEN)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    c.border = B
ws.row_dimensions[2].height = 32

r = 3
for p in plan:
    note = (p["p"].get("note2") or "")
    if p["p"].get("note"):
        note = ("＊" + note) if note else "＊"
    vals = [p["idx"] if "idx" in p else len(plan), p["day"], p["wd"], p["start"], p["end"], p["co"],
            "机构负责人", "人力资源负责人", "我、汪洋、陈信克",
            p["p"]["name"], p["p"]["pos"], p["p"]["lv"], p["p"].get("entry", ""), "面对面/线上会议"]
    vals[0] = r - 2
    for i, v in enumerate(vals, 1):
        c = ws.cell(row=r, column=i, value=v)
        c.font = Font(name=FONT, size=9); c.border = B
        c.alignment = Alignment(horizontal="center" if i not in (6, 7, 8, 9, 11) else "left",
                                vertical="center", wrap_text=i in (7, 8, 9, 11))
    ws.cell(row=r, column=18, value="=IF(COUNT(O{0}:Q{0})=3,ROUND(AVERAGE(O{0}:Q{0}),2),\"\")".format(r))
    ws.cell(row=r, column=19, value="=IF(R{0}=\"\",\"\",IF(AND(R{0}>=3,MIN(O{0}:Q{0})>=2),\"行\",\"不行\"))".format(r))
    for i in (15, 16, 17, 18, 19):
        c = ws.cell(row=r, column=i)
        c.font = Font(name=FONT, size=9); c.border = B
        c.alignment = Alignment(horizontal="center", vertical="center")
    c = ws.cell(row=r, column=21, value=note)
    c.font = Font(name=FONT, size=9); c.border = B
    c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    if (r - 2) % 2 == 0:
        for i in range(1, 22):
            ws.cell(row=r, column=i).fill = PatternFill("solid", fgColor=LIGHT)
    ws.row_dimensions[r].height = 24
    r += 1

ws.freeze_panes = "F3"
ws.auto_filter.ref = "A2:U%d" % (r - 1)

# ---------- Sheet2 ----------
ws2 = wb.create_sheet("02 方式与口径")
ws2.sheet_view.showGridLines = False
for col, wd in {"A": 14, "B": 8, "C": 30, "D": 22, "E": 22, "F": 24, "G": 14}.items():
    ws2.column_dimensions[col].width = wd
ws2.merge_cells("A1:G1")
c = ws2["A1"]; c.value = "沟通方式与判定口径"
c.font = Font(name=FONT, size=13, bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor=GREEN)
c.alignment = Alignment(horizontal="center", vertical="center"); ws2.row_dimensions[1].height = 30

blocks = [
    ("参会人（3 方）", [
        ("机构负责人", "讲业务结果与岗位要求匹配度，对“是否胜任”给结论。"),
        ("人力资源负责人", "讲任职资格、绩效记录、团队反馈与风险点。"),
        ("集团相关方", "我、汪洋、陈信克，负责主持、提问与记录。"),
    ]),
    ("10 分钟结构与分工", [
        ("0–1 分", "说明目的与边界：仅就岗位胜任度作事实性确认，不涉及薪酬、任免与个人评价。"),
        ("1–5 分", "机构负责人、人力资源负责人各 2 分钟，陈述被评估人近半年一项可验证的履职事实，含事项、时间与结果。"),
        ("5–8 分", "按专业技能、管理技能、发展潜力三个维度依次结构化追问，要求以事实与数据作答。"),
        ("8–10 分", "完成三项评分与结论，并以一句事实性表述记录判定依据。"),
    ]),
    ("评分口径", [
        ("专业技能", "岗位核心职责的独立承担能力。"),
        ("管理技能", "目标分解、过程管控、团队建设与跨部门协作。"),
        ("发展潜力", "可承担更高一级职责的事实依据与学习能力。"),
        ("分值", "每项 0–5 分（5 显著超出、3 符合、1 明显不足）；权重各 33%，加权分为三项算术平均。"),
    ]),
    ("结论规则", [
        ("行", "加权分 ≥ 3.0，且三项均不低于 2.0。"),
        ("不行", "加权分 < 3.0，或任一项低于 2.0。"),
        ("依据", "以事实与行为证据表述，不使用评价性形容词。"),
        ("档位", "结论仅设「行 / 不行」两档，不设中间档。"),
    ]),
    ("排期口径", [
        ("总量", "%d 人 × 10 分钟 = %.1f 小时，压缩至 4 天（10-22 至 10-25，含周末）。" % (len(plan), len(plan) * 10 / 60.0)),
        ("每日", "9:00–12:00（18 个档期）+ 13:00 起，中午休息 1 小时，当天排完即止。"),
        ("节点", "10 月 25 日全部完成，每日 16:00–17:00 结束。"),
        ("顺序", "按机构成块，同一机构不跨天，减少换场。"),
        ("方式", "统一为「面对面 / 线上会议」：同城机构安排面对面，异地机构安排线上会议。"),
        ("名单", "在原 MP 名单基础上去掉 13 人；已逐人比对系统后台（同步时间 2026-10-21 18:01）：一致 97 人、岗位更新 38 人、待确认 7 人，详见「03 后台核对」。"),
    ]),
]
r = 3
for title, items in blocks:
    ws2.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
    c = ws2.cell(row=r, column=1, value=title)
    c.font = Font(name=FONT, size=11, bold=True, color=GREEN)
    c.fill = PatternFill("solid", fgColor=CREAM)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws2.row_dimensions[r].height = 24
    r += 1
    for k, v in items:
        ws2.cell(row=r, column=1, value=k).font = Font(name=FONT, size=10, bold=True)
        ws2.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
        c = ws2.cell(row=r, column=2, value=v)
        c.font = Font(name=FONT, size=10)
        c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
        for i in range(1, 8):
            ws2.cell(row=r, column=i).border = B
        ws2.row_dimensions[r].height = 22
        r += 1
    r += 1

# 机构场次表
ws2.cell(row=r, column=1, value="机构场次").font = Font(name=FONT, size=11, bold=True, color=GREEN)
r += 1
head2 = ["机构", "人数", "场次时段", "机构负责人", "人力资源负责人", "集团相关方", "方式"]
for i, h in enumerate(head2, 1):
    c = ws2.cell(row=r, column=i, value=h)
    c.font = Font(name=FONT, size=9, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=GREEN)
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border = B
ws2.row_dimensions[r].height = 22
r += 1
agg = collections.OrderedDict()
for p in plan:
    a = agg.setdefault(p["co"], {"n": 0, "day": p["day"], "wd": p["wd"], "segs": []})
    a["n"] += 1
    t = int(p["start"][:2]) * 60 + int(p["start"][3:])
    if not a["segs"] or t - a["segs"][-1][1] > 10:
        a["segs"].append([t, t + 10])
    else:
        a["segs"][-1][1] = t + 10
for co, a in agg.items():
    seg = " / ".join("%02d:%02d–%02d:%02d" % (x[0] // 60, x[0] % 60, x[1] // 60, x[1] % 60) for x in a["segs"])
    vals = [co, a["n"], "%s（%s）%s" % (a["day"], a["wd"], seg),
            "机构负责人", "人力资源负责人", "我、汪洋、陈信克", "面对面/线上会议"]
    for i, v in enumerate(vals, 1):
        c = ws2.cell(row=r, column=i, value=v)
        c.font = Font(name=FONT, size=9); c.border = B
        c.alignment = Alignment(horizontal="center" if i in (2, 7) else "left", vertical="center", wrap_text=i in (4, 5, 6))
    ws2.row_dimensions[r].height = 24
    r += 1

# ---------- Sheet3 后台核对 ----------
ver = list(csv.DictReader(open("/tmp/mp_verify.csv", encoding="utf-8")))
ws3 = wb.create_sheet("03 后台核对")
ws3.sheet_view.showGridLines = False
h3 = ["序号", "机构（名单）", "姓名", "名单岗位", "名单职级", "后台机构", "后台岗位", "后台职级",
      "后台入职日期", "后台状态", "核对结论", "其他同名在职记录"]
w3 = [6, 14, 10, 28, 9, 14, 28, 9, 13, 9, 16, 44]
for i, x in enumerate(w3, 1):
    ws3.column_dimensions[get_column_letter(i)].width = x
ws3.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(h3))
c = ws3.cell(row=1, column=1, value="名单与系统后台核对明细（%d 人）｜后台同步时间 2026-10-21 18:01" % len(ver))
c.font = Font(name=FONT, size=13, bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor=GREEN)
c.alignment = Alignment(horizontal="center", vertical="center"); ws3.row_dimensions[1].height = 30
for i, h in enumerate(h3, 1):
    c = ws3.cell(row=2, column=i, value=h)
    c.font = Font(name=FONT, size=9, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=GREEN)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    c.border = B
ws3.row_dimensions[2].height = 30
rr = 3
for i, v in enumerate(ver, 1):
    vals = [i, v["co"], v["name"], v["list_pos"], v["list_lv"], v["db_org"], v["db_pos"], v["db_lv"],
            v["db_entry"], v["db_state"], v["status"], v["alt"]]
    for j, x in enumerate(vals, 1):
        c = ws3.cell(row=rr, column=j, value=x)
        c.font = Font(name=FONT, size=9); c.border = B
        c.alignment = Alignment(horizontal="center" if j in (1, 5, 8, 9, 10, 11) else "left",
                                vertical="center", wrap_text=j in (4, 7, 12))
    if v["status"] == "一致":
        ws3.cell(row=rr, column=11).fill = PatternFill("solid", fgColor="E8F2EA")
    elif v["status"] == "岗位更新":
        ws3.cell(row=rr, column=11).fill = PatternFill("solid", fgColor="FBF3E2")
    else:
        ws3.cell(row=rr, column=11).fill = PatternFill("solid", fgColor="F8E4E1")
    ws3.row_dimensions[rr].height = 24
    rr += 1
ws3.freeze_panes = "C3"
ws3.auto_filter.ref = "A2:L%d" % (rr - 1)

ws2.print_area = "A1:G%d" % r
for sh in (ws, ws2, ws3):
    sh.page_setup.orientation = "landscape"; sh.page_setup.paperSize = 9
    sh.sheet_properties.pageSetUpPr.fitToPage = True
    sh.page_setup.fitToWidth = 1; sh.page_setup.fitToHeight = 0
    sh.print_options.horizontalCentered = True
ws.print_title_rows = "2:2"

wb.save(OUT)
print("saved", OUT, len(plan), "人", len(agg), "机构")
