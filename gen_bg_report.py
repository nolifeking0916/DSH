# -*- coding: utf-8 -*-
"""生成「员工景区/度假区/乐园/酒店背景」分析表"""
import json, re, collections, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

SPILL = "/var/folders/gf/k4dsxpz511s5386jkv94mp_m0000gn/T/dsh-spill-jF7mlK/session-68fd6f4ba295/37cd35228569-mcp__hrq-pg__query_sql.txt"
OUT = "/Users/leto/Downloads/员工景区度假区乐园酒店背景分析_20261021.xlsx"

GREEN, CREAM, LIGHT = "1E4634", "F5F0E4", "EDF2EE"
FONT = "微软雅黑"
thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

RAW = json.load(open(SPILL, encoding="utf-8"))
data = [dict(zip(RAW["columns"], r)) for r in RAW["rows"]]

INTERNAL = re.compile(r"(云上|茅森|茅山森林世界|松鼠|星空|景尚|恐龙酒店|恐龙主题度假|大竹海|熊猫部落|半亩田|七星谷)")

RULES = [
    ("乐园", re.compile(r"(乐园|主题公园|游乐园|水上乐园|欢乐谷|方特|迪士尼|环球影城|海洋公园|野生动物园|动物园|恐龙园|嬉戏谷|长隆|童世界|融创文旅城|融创乐园|世嘉|影视乐园|水世界|海洋馆|欢乐世界|环球恐龙城|大马戏|圣亚|大白鲸|动物王国)")),
    ("景区", re.compile(r"(景区|风景区|旅游区|索道|盐湖城|百草园|百草原|乌镇|水镇|拈花湾|孝道园|龙之梦|天目湖|千岛湖|古镇|古城|文化园|生态园|漂流|旅游发展|旅游开发|旅游投资|文化旅游|文旅|华侨城|瘦西湖|山景区|宝盛园|大峡谷|天门山|宋城|千古情|万岁山|婺女洲|葛仙山|启封故园|尼山圣境|炭河|影视城|横店)")),
    ("度假区", re.compile(r"(度假区|度假村|度假酒店|温泉|山庄|疗养|庄园|度假)")),
    ("酒店", re.compile(r"(酒店|宾馆|饭店|客栈|民宿|大酒店|酒店管理|酒店公寓|万豪|希尔顿|喜来登|洲际|凯悦|香格里拉|温德姆|华美达|维也纳|全季|如家|汉庭|亚朵|格林豪泰|锦江|开元|君澜|铂尔曼|诺富特|皇冠假日|智选假日|豪生|万丽|悦榕庄|凯莱|远洲|白天鹅|丽笙|建国饭店|维景|南苑|裸心|悦华|嘉华|福朋|凯宾斯基|丽晶)")),
]
ORDER = ["乐园", "景区", "度假区", "酒店"]
LABEL = {"乐园": "乐园", "景区": "景区", "度假区": "度假区", "酒店": "酒店"}

def cats(c):
    c = (c or "").strip()
    return [k for k, rx in RULES if rx.search(c)]

def dpart(s):
    return (s or "")[:10]

# 明细命中行
detail = []
for d in data:
    c = d["prev_company"] or ""
    cs = cats(c)
    if not cs:
        continue
    d2 = dict(d)
    d2["cats"] = cs
    d2["internal"] = bool(INTERNAL.search(c))
    d2["years"] = float(d["prev_years"]) if d["prev_years"] else 0.0
    detail.append(d2)

# 人员汇总
per = {}
for d in detail:
    p = per.setdefault(d["id"], {
        "姓名": d["name"], "工号": d["number"], "机构": d["company"], "部门": d["division"],
        "职位": d["position"], "职级": d["level"], "入职": dpart(d["entry_date"]),
        "cats": set(), "rows": [], "internal_only": True,
    })
    p["cats"].update(d["cats"])
    p["rows"].append(d)
    if not d["internal"]:
        p["internal_only"] = False

def main_cat(cs):
    for k in ORDER:
        if k in cs:
            return LABEL[k]
    return ""

persons = []
for pid, p in per.items():
    rows = sorted(p["rows"], key=lambda x: x["prev_end"] or x["prev_start"] or "", reverse=True)
    p["主类别"] = main_cat(p["cats"])
    p["类别"] = "／".join(LABEL[k] for k in ORDER if k in p["cats"])
    p["单位"] = "；".join(dict.fromkeys(r["prev_company"].strip() for r in rows))
    p["岗位"] = "；".join(dict.fromkeys((r["prev_position"] or "").strip() for r in rows if (r["prev_position"] or "").strip()))
    p["段数"] = len(rows)
    p["年限"] = round(sum(r["years"] for r in rows), 1)
    p["最近结束"] = next((dpart(r["prev_end"]) for r in rows if r["prev_end"]), "")
    p["仅内部"] = "是" if p["internal_only"] else "否"
    persons.append(p)

persons.sort(key=lambda x: (ORDER.index(x["主类别"].split("/")[0]) if x["主类别"] else 9,
                            -x["年限"], x["机构"], x["姓名"]))

cat_count = {k: sum(1 for p in persons if k in p["cats"]) for k in ORDER}
any_n = len(persons)
internal_only_n = sum(1 for p in persons if p["仅内部"] == "是")

# 机构统计
wb = Workbook()

def style_header(ws, row, cols):
    for i in range(1, cols + 1):
        c = ws.cell(row=row, column=i)
        c.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=GREEN)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER

# ---------- Sheet1 汇总 ----------
ws = wb.active
ws.title = "01 汇总"
ws.sheet_view.showGridLines = False
for col, w in {"A": 22, "B": 14, "C": 14, "D": 14, "E": 40}.items():
    ws.column_dimensions[col].width = w
ws.merge_cells("A1:E1")
c = ws["A1"]; c.value = "员工景区／度假区／乐园／酒店背景分析"
c.font = Font(name=FONT, size=16, bold=True, color="FFFFFF")
c.fill = PatternFill("solid", fgColor=GREEN)
c.alignment = Alignment(horizontal="center", vertical="center")
ws.row_dimensions[1].height = 40

lines = [
    ("数据源", "hr_persons_all（企业后台人员主数据，每日同步）＋ work_experience（入职前工作经历）"),
    ("在职口径", "state = 0 且 leaveDate 为空"),
    ("在职人数", "887 人"),
    ("有工作经历记录", "822 人（93%），其余 65 人数据库无经历记录，无法判定"),
    ("判定规则", "按经历单位名称关键词归类，可多类并存；含在本集团内单位的前段经历（另列「仅内部」标识）"),
]
r = 3
for k, v in lines:
    ws.cell(row=r, column=1, value=k).font = Font(name=FONT, size=10, bold=True, color=GREEN)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
    c = ws.cell(row=r, column=2, value=v)
    c.font = Font(name=FONT, size=10)
    c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[r].height = 30 if len(v) > 45 else 22
    r += 1

r += 1
ws.cell(row=r, column=1, value="背景类别").font = Font(name=FONT, size=11, bold=True, color=GREEN)
r += 1
hdr = ["类别", "人数", "占全体在职", "占有人数/822", "说明"]
for i, h in enumerate(hdr, 1):
    ws.cell(row=r, column=i, value=h)
style_header(ws, r, 5); r += 1
descs = {
    "乐园": "主题乐园、游乐园、水上乐园、动物园、海洋公园、演艺景区",
    "景区": "景区、风景区、旅游度假区（非酒店）、索道、文旅景区开发",
    "度假区": "度假区、度假村、温泉度假酒店、山庄",
    "酒店": "酒店、宾馆、饭店、民宿、酒店管理公司",
}
ws.cell(row=r, column=1, value="命中任一类别（去重）")
ws.cell(row=r, column=2, value=any_n)
ws.cell(row=r, column=3, value=round(any_n / 887 * 100, 1) / 100)
ws.cell(row=r, column=4, value=round(any_n / 822 * 100, 1) / 100)
ws.cell(row=r, column=5, value="至少有一段相关经历")
for i in range(1, 6):
    cell = ws.cell(row=r, column=i); cell.border = BORDER
    cell.font = Font(name=FONT, size=10, bold=True)
    cell.alignment = Alignment(horizontal="center" if i in (2, 3, 4) else "left", vertical="center")
    if i in (3, 4):
        cell.number_format = "0.0%"
r += 1
for k in ORDER:
    ws.cell(row=r, column=1, value=LABEL[k])
    ws.cell(row=r, column=2, value=cat_count[k])
    ws.cell(row=r, column=3, value=round(cat_count[k] / 887 * 100, 1) / 100)
    ws.cell(row=r, column=4, value=round(cat_count[k] / 822 * 100, 1) / 100)
    ws.cell(row=r, column=5, value=descs[k])
    for i in range(1, 6):
        cell = ws.cell(row=r, column=i); cell.border = BORDER
        cell.font = Font(name=FONT, size=10)
        cell.alignment = Alignment(horizontal="center" if i in (2, 3, 4) else "left", vertical="center", wrap_text=True)
        if i in (3, 4):
            cell.number_format = "0.0%"
    r += 1
ws.cell(row=r, column=1, value="其中：仅本集团内部经历").font = Font(name=FONT, size=9, italic=True, color="595959")
ws.cell(row=r, column=2, value=internal_only_n).font = Font(name=FONT, size=9, color="595959")
ws.cell(row=r, column=5, value="前段经历只有云上草原度假村、星空／松鼠／恐龙酒店等内部单位，可按需剔除").font = Font(name=FONT, size=9, color="595959")

# -------- Sheet2 名单 --------
ws2 = wb.create_sheet("02 命中人员名单")
ws2.sheet_view.showGridLines = False
h2 = ["序号", "姓名", "工号", "机构", "部门", "职位", "职级", "入职日期", "背景类别", "主类别",
      "相关背景单位", "对应岗位", "经历段数", "相关累计年限", "仅集团内"]
w2 = [6, 9, 9, 11, 11, 20, 10, 12, 22, 12, 46, 34, 9, 11, 9]
for i, wd in enumerate(w2, 1):
    ws2.column_dimensions[get_column_letter(i)].width = wd
ws2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(h2))
c = ws2.cell(row=1, column=1, value="命中人员名单（%d 人，按主类别／累计年限排序）" % len(persons))
c.font = Font(name=FONT, size=13, bold=True, color="FFFFFF")
c.fill = PatternFill("solid", fgColor=GREEN)
c.alignment = Alignment(horizontal="center", vertical="center")
ws2.row_dimensions[1].height = 32
for i, h in enumerate(h2, 1):
    ws2.cell(row=2, column=i, value=h)
style_header(ws2, 2, len(h2))
rr = 3
for idx, p in enumerate(persons, 1):
    vals = [idx, p["姓名"], p["工号"], p["机构"], p["部门"], p["职位"], p["职级"], p["入职"],
            p["类别"], p["主类别"], p["单位"], p["岗位"], p["段数"], p["年限"], p["仅内部"]]
    for i, v in enumerate(vals, 1):
        cell = ws2.cell(row=rr, column=i, value=v)
        cell.font = Font(name=FONT, size=9)
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center" if i in (1, 2, 3, 8, 9, 10, 13, 14, 15) else "left",
                                   vertical="center", wrap_text=i in (11, 12))
        if idx % 2 == 0:
            cell.fill = PatternFill("solid", fgColor=LIGHT)
    ws2.row_dimensions[rr].height = 28
    rr += 1
ws2.freeze_panes = "C3"
ws2.auto_filter.ref = "A2:O%d" % (rr - 1)

# -------- Sheet3 明细 --------
ws3 = wb.create_sheet("03 经历明细")
ws3.sheet_view.showGridLines = False
h3 = ["序号", "姓名", "工号", "现机构", "现职位", "背景单位", "背景岗位", "开始", "结束", "年限", "命中类别", "集团内"]
w3 = [6, 9, 9, 11, 20, 32, 22, 12, 12, 8, 18, 8]
for i, wd in enumerate(w3, 1):
    ws3.column_dimensions[get_column_letter(i)].width = wd
ws3.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(h3))
c = ws3.cell(row=1, column=1, value="命中经历明细（%d 段）" % len(detail))
c.font = Font(name=FONT, size=13, bold=True, color="FFFFFF")
c.fill = PatternFill("solid", fgColor=GREEN)
c.alignment = Alignment(horizontal="center", vertical="center")
ws3.row_dimensions[1].height = 32
for i, h in enumerate(h3, 1):
    ws3.cell(row=2, column=i, value=h)
style_header(ws3, 2, len(h3))
order_key = {p["姓名"] + p["工号"]: i for i, p in enumerate(persons)}
detail.sort(key=lambda d: (order_key.get(d["name"] + d["number"], 999), d["prev_start"] or ""))
rr = 3
for idx, d in enumerate(detail, 1):
    vals = [idx, d["name"], d["number"], d["company"], d["position"], d["prev_company"], d["prev_position"],
            dpart(d["prev_start"]), dpart(d["prev_end"]), d["years"],
            "／".join(LABEL[k] for k in ORDER if k in d["cats"]), "是" if d["internal"] else "否"]
    for i, v in enumerate(vals, 1):
        cell = ws3.cell(row=rr, column=i, value=v)
        cell.font = Font(name=FONT, size=9)
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center" if i in (1, 2, 3, 8, 9, 10, 11, 12) else "left",
                                   vertical="center", wrap_text=i in (5, 6, 7))
        if idx % 2 == 0:
            cell.fill = PatternFill("solid", fgColor=LIGHT)
    ws3.row_dimensions[rr].height = 24
    rr += 1
ws3.freeze_panes = "C3"
ws3.auto_filter.ref = "A2:L%d" % (rr - 1)

# -------- Sheet4 机构分布 --------
ws4 = wb.create_sheet("04 机构分布")
ws4.sheet_view.showGridLines = False
ACTIVE = {"云上景区": (171, 162), "松鼠酒店": (159, 156), "茅森景区": (99, 98), "恐龙酒店": (64, 63),
          "集团部门": (53, 49), "云上余村": (48, 47), "星空酒店": (47, 47), "熊猫部落": (45, 31),
          "茅森酒店": (41, 41), "云上商管": (37, 35), "浙江营销": (34, 32), "中国大竹海": (24, 4),
          "聚力旅行社": (23, 17), "研创院": (21, 21), "工程管理分公司": (12, 11), "七星谷漂流": (3, 3),
          "安吉半亩田": (2, 1), "云上草原七星谷": (2, 2), "云上民宿": (2, 2)}
h4 = ["机构", "在职人数", "有经历记录", "命中人数", "命中率（占在职）", "占命中总数"]
for i, wd in enumerate([16, 10, 12, 10, 14, 12], 1):
    ws4.column_dimensions[get_column_letter(i)].width = wd
ws4.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)
c = ws4.cell(row=1, column=1, value="命中人员机构分布")
c.font = Font(name=FONT, size=13, bold=True, color="FFFFFF")
c.fill = PatternFill("solid", fgColor=GREEN)
c.alignment = Alignment(horizontal="center", vertical="center")
ws4.row_dimensions[1].height = 30
for i, h in enumerate(h4, 1):
    ws4.cell(row=2, column=i, value=h)
style_header(ws4, 2, 6)
by_co = collections.Counter(p["机构"] for p in persons)
rr = 3
for co, (tot, has) in sorted(ACTIVE.items(), key=lambda kv: -by_co[kv[0]]):
    n = by_co.get(co, 0)
    vals = [co, tot, has, n, round(n / tot, 3) if tot else 0, round(n / any_n, 3) if any_n else 0]
    for i, v in enumerate(vals, 1):
        cell = ws4.cell(row=rr, column=i, value=v)
        cell.font = Font(name=FONT, size=10)
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center" if i > 1 else "left", vertical="center")
        if i in (5, 6):
            cell.number_format = "0.0%"
    rr += 1
ws4.cell(row=rr, column=1, value="合计").font = Font(name=FONT, size=10, bold=True)
ws4.cell(row=rr, column=2, value=887).font = Font(name=FONT, size=10, bold=True)
ws4.cell(row=rr, column=3, value=822).font = Font(name=FONT, size=10, bold=True)
ws4.cell(row=rr, column=4, value=any_n).font = Font(name=FONT, size=10, bold=True)
ws4.cell(row=rr, column=5, value=round(any_n / 887, 3)).font = Font(name=FONT, size=10, bold=True)
ws4.cell(row=rr, column=6, value=1.0).font = Font(name=FONT, size=10, bold=True)
for i in range(1, 7):
    ws4.cell(row=rr, column=i).border = BORDER
    if i in (5, 6):
        ws4.cell(row=rr, column=i).number_format = "0.0%"

for sh in (ws2, ws3, ws4):
    sh.page_setup.orientation = "landscape"
    sh.page_setup.paperSize = 9
    sh.sheet_properties.pageSetUpPr.fitToPage = True
    sh.page_setup.fitToWidth = 1
    sh.page_setup.fitToHeight = 0
    sh.print_options.horizontalCentered = True

wb.save(OUT)

# 控制台摘要
lev = collections.Counter("管理序列" if p["职级"].startswith("管理") else ("专业序列" if p["职级"].startswith("专业") else "其他") for p in persons)
top_units = collections.Counter()
for d in detail:
    if not d["internal"]:
        top_units[d["prev_company"].strip()] += 1
print(json.dumps({
    "output": OUT,
    "active": 887, "with_resume": 822, "hit_persons": any_n,
    "internal_only": internal_only_n,
    "cats": cat_count,
    "main": dict(collections.Counter(p["主类别"] for p in persons)),
    "level": dict(lev),
    "top_units": top_units.most_common(12),
    "detail_rows": len(detail),
}, ensure_ascii=False, indent=1))
