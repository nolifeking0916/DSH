# -*- coding: utf-8 -*-
"""生成《10 项制度（试行稿）征求意见收集表》Excel"""
import os
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

GREEN = "1E4634"
CREAM = "F5F0E4"
LIGHT = "EDF2EE"
GRAY_TXT = "595959"

FONT_CN = os.environ.get("FORM_FONT", "微软雅黑")

thin = Side(style="thin", color="BFBFBF")
border = Border(left=thin, right=thin, top=thin, bottom=thin)

DOCS = [
    ("1", "7-1", "部门设置标准细则"),
    ("2", "7-31", "员工作休细则"),
    ("3", "9-0", "招聘管理制度（总则）"),
    ("4", "11-0", "绩效考核管理制度（总则）"),
    ("5", "11-2", "绩效考核细则"),
    ("6", "12-0", "薪酬管理制度（总则）"),
    ("7", "36-0", "晋升管理制度（总则）"),
    ("8", "36-1", "O序列员工晋升管理细则"),
    ("9", "36-2", "P序列员工晋升管理细则"),
    ("10", "36-3", "M序列员工晋升管理细则"),
]

OPTIONS = "无,有疑问,有建议,疑问和建议都有"

wb = Workbook()

# ---------------- Sheet 1 说明 ----------------
ws = wb.active
ws.title = "01 填写说明"
ws.sheet_view.showGridLines = False
ws.column_dimensions["A"].width = 6
ws.column_dimensions["B"].width = 12
ws.column_dimensions["C"].width = 34
ws.column_dimensions["D"].width = 16

ws.merge_cells("A1:D1")
c = ws["A1"]
c.value = "制度（试行稿）征求意见收集表"
c.font = Font(name=FONT_CN, size=18, bold=True, color="FFFFFF")
c.fill = PatternFill("solid", fgColor=GREEN)
c.alignment = Alignment(horizontal="center", vertical="center")
ws.row_dimensions[1].height = 46

ws.merge_cells("A2:D2")
c = ws["A2"]
c.value = "浙江云上文旅集团股份有限公司 · 集团行政管理中心行政人事部"
c.font = Font(name=FONT_CN, size=10, color="FFFFFF")
c.fill = PatternFill("solid", fgColor=GREEN)
c.alignment = Alignment(horizontal="center", vertical="center")
ws.row_dimensions[2].height = 24

intro = [
    ("", ""),
    ("一、收集范围", ""),
    ("", "2026 年 10 月 8 日 / 10 月 9 日修订的 10 项制度试行稿（清单见下表）。"),
    ("二、答复方式", ""),
    ("", "每一项制度设两个问题："),
    ("", "第一题（单选）：对该制度是否有疑问和建议，选项为「无 / 有疑问 / 有建议 / 疑问和建议都有」。"),
    ("", "第二题（文字）：如有疑问或建议，请具体描述；第一题选「无」的，第二题可留空。"),
    ("三、填写要求", ""),
    ("", "1. 涉及具体条款的，请注明条款序号（如「第四条」「五、调薪规则第 1 点」），便于逐条答复。"),
    ("", "2. 建议尽量写清「问题是什么 + 建议怎么改」，避免只写「不合理」「有意见」。"),
    ("", "3. 多项制度都有意见的，逐行填写即可；也可只填有意见的条目。"),
    ("", "4. 涉及个人薪酬、岗位等敏感信息，可只写制度条款问题，不必写个人情况。"),
    ("四、反馈期限", ""),
    ("", "自下发之日起至 2026 年 10 月 30 日止。汇总答复由集团行政管理中心行政人事部统一反馈。"),
    ("五、收集方式", ""),
    ("", "线上：按「03 企微收集表题目」在企业微信「收集表」中建表，发至各部门/机构填写；"),
    ("", "线下：填写本工作簿「02 收集表」，回传集团行政管理中心行政人事部。"),
]

r = 3
for a, b in intro:
    if a:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        cell = ws.cell(row=r, column=1, value=a)
        cell.font = Font(name=FONT_CN, size=11, bold=True, color=GREEN)
        cell.fill = PatternFill("solid", fgColor=CREAM)
        cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[r].height = 24
    else:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        cell = ws.cell(row=r, column=1, value=b)
        cell.font = Font(name=FONT_CN, size=10, color=GRAY_TXT)
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        ws.row_dimensions[r].height = 20 if len(b) < 60 else 32
    r += 1

r += 1
hdr = ["序号", "制度编号", "制度名称", "文件版本"]
for i, h in enumerate(hdr, start=1):
    cell = ws.cell(row=r, column=i, value=h)
    cell.font = Font(name=FONT_CN, size=10, bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor=GREEN)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = border
ws.row_dimensions[r].height = 26
hdr_row = r
r += 1
for no, code, name in DOCS:
    vals = [no, code, name, "试行稿 2026.10.8" if code != "11-2" else "试行稿 2026.10.9"]
    for i, v in enumerate(vals, start=1):
        cell = ws.cell(row=r, column=i, value=v)
        cell.font = Font(name=FONT_CN, size=10, color="262626")
        cell.alignment = Alignment(horizontal="center" if i != 3 else "left",
                                   vertical="center", indent=0 if i != 3 else 1)
        cell.border = border
        if (r - hdr_row) % 2 == 0:
            cell.fill = PatternFill("solid", fgColor=LIGHT)
    ws.row_dimensions[r].height = 22
    r += 1

# ---------------- Sheet 2 收集表 ----------------
ws2 = wb.create_sheet("02 收集表")
ws2.sheet_view.showGridLines = False
widths = {"A": 6, "B": 10, "C": 30, "D": 24, "E": 56, "F": 12}
for k, v in widths.items():
    ws2.column_dimensions[k].width = v

ws2.merge_cells("A1:F1")
c = ws2["A1"]
c.value = "制度（试行稿）征求意见收集表"
c.font = Font(name=FONT_CN, size=16, bold=True, color="FFFFFF")
c.fill = PatternFill("solid", fgColor=GREEN)
c.alignment = Alignment(horizontal="center", vertical="center")
ws2.row_dimensions[1].height = 38

info = [("填表人：", "A2", "B2"), ("所属机构：", "C2", "D2"), ("部门/岗位：", "A3", "B3"), ("填写日期：", "C3", "D3")]
for label, lc, vc in info:
    cell = ws2[lc]
    cell.value = label
    cell.font = Font(name=FONT_CN, size=10, bold=True, color=GREEN)
    cell.alignment = Alignment(horizontal="right", vertical="center")
    v = ws2[vc]
    v.border = Border(bottom=thin)
    v.font = Font(name=FONT_CN, size=10, color="262626")
ws2.row_dimensions[2].height = 26
ws2.row_dimensions[3].height = 26

ws2.merge_cells("A4:F4")
c = ws2["A4"]
c.value = "填写提示：第一题单选「无 / 有疑问 / 有建议 / 疑问和建议都有」；第二题仅在非「无」时填写，注明条款序号更便于答复。"
c.font = Font(name=FONT_CN, size=9, color=GRAY_TXT)
c.fill = PatternFill("solid", fgColor=CREAM)
c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
ws2.row_dimensions[4].height = 24

headers = ["序号", "制度编号", "制度名称", "第一题：是否有疑问和建议（单选）",
           "第二题：如有，请文字描述（注明条款）", "备注（内部）"]
for i, h in enumerate(headers, start=1):
    cell = ws2.cell(row=5, column=i, value=h)
    cell.font = Font(name=FONT_CN, size=10, bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor=GREEN)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = border
ws2.row_dimensions[5].height = 40

start = 6
for idx, (no, code, name) in enumerate(DOCS):
    row = start + idx
    ws2.cell(row=row, column=1, value=int(no))
    ws2.cell(row=row, column=2, value=code)
    ws2.cell(row=row, column=3, value=name)
    ws2.cell(row=row, column=4, value=None)
    ws2.cell(row=row, column=5, value=None)
    ws2.cell(row=row, column=6, value=None)
    for col in range(1, 7):
        cell = ws2.cell(row=row, column=col)
        cell.border = border
        cell.font = Font(name=FONT_CN, size=10, color="262626")
        cell.alignment = Alignment(horizontal="center" if col in (1, 2, 6) else "left",
                                   vertical="center", wrap_text=(col == 5),
                                   indent=1 if col in (3, 4, 5) else 0)
        if idx % 2 == 1:
            cell.fill = PatternFill("solid", fgColor=LIGHT)
    ws2.row_dimensions[row].height = 42

end = start + len(DOCS) - 1
dv = DataValidation(type="list", formula1='"%s"' % OPTIONS, allow_blank=True,
                    showErrorMessage=True, errorTitle="请选择",
                    error="请从下拉选项中选择：无 / 有疑问 / 有建议 / 疑问和建议都有")
ws2.add_data_validation(dv)
dv.add("D%d:D%d" % (start, end))

ws2.freeze_panes = "D6"
ws2.auto_filter.ref = "A5:F%d" % end

# ---------------- Sheet 3 企微收集表题目 ----------------
ws3 = wb.create_sheet("03 企微收集表题目")
ws3.sheet_view.showGridLines = False
w3 = {"A": 6, "B": 8, "C": 10, "D": 52, "E": 34, "F": 10, "G": 30}
for k, v in w3.items():
    ws3.column_dimensions[k].width = v

ws3.merge_cells("A1:G1")
c = ws3["A1"]
c.value = "企业微信「收集表」题目清单（共 20 题，按制度 1→10 顺序录入）"
c.font = Font(name=FONT_CN, size=14, bold=True, color="FFFFFF")
c.fill = PatternFill("solid", fgColor=GREEN)
c.alignment = Alignment(horizontal="center", vertical="center")
ws3.row_dimensions[1].height = 36

note = ("建议设置：① 收集表说明填「反馈有效期至 2026 年 10 月 30 日」；② 题 1-1 至 10-1 全部必答；"
        "③ 题 *-2 设为「第一题选『无』则跳过」；④ 可选开启匿名收集；⑤ 回收后按「制度 × 选项」统计。")
ws3.merge_cells("A2:G2")
c = ws3["A2"]
c.value = note
c.font = Font(name=FONT_CN, size=9, color=GRAY_TXT)
c.fill = PatternFill("solid", fgColor=CREAM)
c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
ws3.row_dimensions[2].height = 32

h3 = ["序号", "题号", "题型", "题目", "选项 / 填写要求", "必答", "显示逻辑"]
for i, h in enumerate(h3, start=1):
    cell = ws3.cell(row=3, column=i, value=h)
    cell.font = Font(name=FONT_CN, size=10, bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor=GREEN)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = border
ws3.row_dimensions[3].height = 26

row = 4
n = 1
for no, code, name in DOCS:
    # 单选
    vals = [n, "%s-1" % no, "单选", "%s/10　《%s》（%s）：您是否有疑问或建议？" % (no, name, code),
            "无 / 有疑问 / 有建议 / 疑问和建议都有", "是", "无"]
    # 文本
    vals2 = [n + 1, "%s-2" % no, "多行文本", "%s/10　《%s》：如有疑问或建议，请具体描述（建议注明条款序号）" % (no, name),
             "自由填写，建议 10-300 字；可写「问题 + 建议怎么改」", "否", "第 %s-1 题选「无」时跳过" % no]
    for v in (vals, vals2):
        for i, val in enumerate(v, start=1):
            cell = ws3.cell(row=row, column=i, value=val)
            cell.font = Font(name=FONT_CN, size=10, color="262626")
            cell.alignment = Alignment(horizontal="center" if i in (1, 2, 3, 6) else "left",
                                       vertical="center", wrap_text=(i in (4, 5, 7)),
                                       indent=1 if i in (4, 5, 7) else 0)
            cell.border = border
        ws3.row_dimensions[row].height = 40 if v is vals else 40
        row += 1
    n += 2

ws3.freeze_panes = "A4"

def page_setup(sheet, landscape=True, area=None):
    sheet.page_setup.orientation = "landscape" if landscape else "portrait"
    sheet.page_setup.paperSize = 9  # A4
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_options.horizontalCentered = True
    sheet.page_margins.left = 0.4
    sheet.page_margins.right = 0.4
    sheet.page_margins.top = 0.5
    sheet.page_margins.bottom = 0.5
    if area:
        sheet.print_area = area

page_setup(ws, landscape=True, area="A1:D%d" % ws.max_row)
page_setup(ws2, landscape=True, area="A1:F%d" % end)
page_setup(ws3, landscape=True, area="A1:G%d" % ws3.max_row)
ws2.print_title_rows = "5:5"
ws3.print_title_rows = "3:3"

out = os.environ.get("FORM_OUT", "/Users/leto/Downloads/制度征求意见收集表_10项制度_20261021.xlsx")
wb.save(out)
print("saved:", out, os.path.getsize(out))
