#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""施测人报告（Word + PDF）生成器 —— 票 #24 后续 / 报告重做。

从**结果 JSON**（产品 `resultObj()` 的格式）生成一份给施测人用的正式报告：
Word（可读、可批注、可归档）+ PDF（可打印、可签字）。

与产品内 HTML 报告的关系：这是**并列的归档件**，产品单文件双入口不动（ADR-0001）。
本脚本只读题库取解析文案，不改题库、不改裁定表、不改成品。

四件本轮修掉的毛病（用户 2026-10-24 反馈）：
  1. 等级徽章「卡边」：HTML 用 border-radius:999px 的胶囊 + padding:0 10px，
     2 个汉字落在圆弧内侧 → 这里改用**底纹单元格**，物理上不可能被裁。
  2. 蛛网图与推理分对不上：HTML 的雷达画的是**模型百分位**、数值标签还塌在画布顶边
     （漏了 p2[1] 的偏移），下面的维度行只写**正确数/总题数** → 统一成**百分位**：
     与维度表同口径。
  3. 版面不专业：章节另起页、表头跨页重复、数字等宽右对齐、页脚合规声明每页在场。
  4. 错题回顾：一页 4400 字的文字墙 → **整块去掉**（用户明确不要）。报告只给
     结果、对结果的解析、对整个候选人的判断。

用法：
    python3 src/build_report_docx.py --json pilot/out/模拟试测_结果JSON_样例.json
产物：
    reports/施测人报告_<code>_<日期>.docx 与 .pdf
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTDIR = os.path.join(ROOT, "reports")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SOFFICE = "/opt/homebrew/bin/soffice"
PDFTOTEXT = "/opt/homebrew/bin/pdftotext"

# ---- 集团 VI（唯一色板来源：src/tokens.css；本页只引用不改） ----
GREEN = "1E4634"   # 深绿：标题带 / 表头底 / 判定块
GREEN2 = "2A5C42"  # 次级绿
GOLD = "C9A55C"    # 金：分隔线 / 强调（浅底不作文字色）
CREAM = "F5F0E4"   # 米白：深底上的文字 / 浅块底
PAPER = "FAF9F4"   # 纸白
INK = "16241C"     # 正文（与视觉模板 src/report_template.css 的 --label 同值）
INK2 = "3C4B43"    # 次级文字（--label-secondary）
LINE = "E3E8E4"    # 分隔线（--separator）
SAND = "6E5B36"    # 浅底上的小字（6.20:1）

LV = {  # 等级底色（tokens.css 的 --lv-*-bg）
    "顶尖": "E5F1EB", "优秀": "E5F1EB", "良好": "EFF1EF",
    "合格": "F4EEE0", "待提升": "FBEDEA",
}
LV_INK = {
    "顶尖": GREEN, "优秀": "1B7A56", "良好": GREEN2,
    "合格": SAND, "待提升": "8E2F26",
}
# 字族 ≤ 2（Apple HIG Typography「字族越少越好」）：
# 正文与标题同用一套苹方（层级靠字重与字号，不靠换字体），
# 数字用 Georgia —— 本身就是等宽数字，表格里的数字不会左右跳。
# ⚠️ 授权红线：网页端不可内嵌 SF 字体文件；Word 里写系统字体名即可，不分发字体。
CN_FONT = "PingFang SC"     # 正文
CN_HEAD = "PingFang SC"     # 标题 / 表头（靠字重区分层级）
EN_FONT = "Georgia"         # 数字（等宽数字）
ORDER = ["待提升", "合格", "良好", "优秀", "顶尖"]

FOOT_LINES = [
    "浙江云上文旅集团 · 集团行政人事部 ｜ 本报告由本地单文件测评结果生成，不上传服务器",
    "心理测评结果不得作为录用唯一依据；本测试不构成医学或心理诊断；本产品不设淘汰线",
]


# ============================================================ 低层排版工具
def _el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn("w:" + k), v)
    return e


def shade(cell, hexcolor):
    cell._tc.get_or_add_tcPr().append(_el("w:shd", val="clear", color="auto", fill=hexcolor))


def cell_margins(cell, top=60, left=110, bottom=60, right=110):
    mar = _el("w:tcMar")
    for k, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        mar.append(_el("w:" + k, w=str(v), type="dxa"))
    cell._tc.get_or_add_tcPr().append(mar)


def table_borders(table, color=LINE, sz=4, inside=True):
    borders = _el("w:tblBorders")
    edges = ["top", "left", "bottom", "right"] + (["insideH", "insideV"] if inside else [])
    for e in edges:
        borders.append(_el("w:" + e, val="single", sz=str(sz), space="0", color=color))
    table._tbl.tblPr.append(borders)


def no_borders(table):
    borders = _el("w:tblBorders")
    for e in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        borders.append(_el("w:" + e, val="none", sz="0", space="0", color="auto"))
    table._tbl.tblPr.append(borders)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    trPr.append(_el("w:tblHeader", val="true"))


def cant_split(row):
    row._tr.get_or_add_trPr().append(_el("w:cantSplit", val="true"))


def run_fmt(run, size=10.5, bold=False, color=INK, cn=CN_FONT, en=EN_FONT, italic=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)
    run.font.name = en
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = _el("w:rFonts")
        rpr.insert(0, rf)
    # 中文字体是 w:rFonts 的**属性**，不是子元素。
    # 写成 <w:eastAsia w:val="…"/> 会被 LibreOffice 忽略 → 中文回退到拉丁/希伯来字体 →
    # 整篇豆腐块（这坑踩过一次，别再犯）。
    rf.set(qn("w:ascii"), en)
    rf.set(qn("w:hAnsi"), en)
    rf.set(qn("w:eastAsia"), cn)
    rf.set(qn("w:cs"), en)
    for child in list(rf):
        if child.tag == qn("w:eastAsia"):
            rf.remove(child)
    return run


def cell_text(cell, text, size=10.5, bold=False, color=INK, cn=CN_FONT, en=EN_FONT,
              align="left", space_after=0):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = {"left": WD_ALIGN_PARAGRAPH.LEFT, "right": WD_ALIGN_PARAGRAPH.RIGHT,
                   "center": WD_ALIGN_PARAGRAPH.CENTER}[align]
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(space_after)
    pf.line_spacing = 1.35
    run_fmt(p.add_run(text), size=size, bold=bold, color=color, cn=cn, en=en)
    return p


def para(doc, text="", size=10.5, bold=False, color=INK, cn=CN_FONT, en=EN_FONT,
         align="left", before=0, after=6, indent=0, line=1.5):
    p = doc.add_paragraph()
    p.alignment = {"left": WD_ALIGN_PARAGRAPH.LEFT, "right": WD_ALIGN_PARAGRAPH.RIGHT,
                   "center": WD_ALIGN_PARAGRAPH.CENTER, "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}[align]
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    if indent:
        pf.left_indent = Cm(indent)
    if text:
        run_fmt(p.add_run(text), size=size, bold=bold, color=color, cn=cn, en=en)
    return p


def rich(doc, parts, size=10.5, align="left", before=0, after=6, indent=0, line=1.5):
    """parts: [(text, {opts}), ...]"""
    p = doc.add_paragraph()
    p.alignment = {"left": WD_ALIGN_PARAGRAPH.LEFT, "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
                   "center": WD_ALIGN_PARAGRAPH.CENTER}[align]
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    if indent:
        pf.left_indent = Cm(indent)
    for text, opts in parts:
        o = dict(size=size)
        o.update(opts)
        run_fmt(p.add_run(text), **o)
    return p


def keep_next(p):
    p.paragraph_format.keep_with_next = True


def page_break(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.add_run().add_break(WD_BREAK.PAGE)


def rule(doc, color=GOLD, size=10, after=8):
    """一段式细金线（用下边框的空段落画）。"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(after)
    pPr = p._p.get_or_add_pPr()
    bdr = _el("w:pBdr")
    bdr.append(_el("w:bottom", val="single", sz=str(size), space="1", color=color))
    pPr.append(bdr)
    return p


def field(paragraph, code):
    fld = _el("w:fldSimple", instr=code)
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rpr.append(_el("w:noProof"))
    sz = _el("w:sz", val="16")
    rpr.append(sz)
    r.append(rpr)
    t = OxmlElement("w:t")
    t.text = "1"
    r.append(t)
    fld.append(r)
    paragraph._p.append(fld)


# ============================================================ 组件
def h1(doc, text, num=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(2)
    pf.keep_with_next = True
    if num:
        run_fmt(p.add_run(num + "  "), size=16.5, bold=True, color=GOLD, cn=CN_HEAD)
    run_fmt(p.add_run(text), size=16.5, bold=True, color=GREEN, cn=CN_HEAD)
    rule(doc, GOLD, 8, after=10)
    return p


def h2(doc, text):
    p = para(doc, text, size=12.75, bold=True, color=GREEN, cn=CN_HEAD, before=12, after=6)
    keep_next(p)
    return p


def kv_table(doc, rows, widths=(4.2, 11.0), header=None):
    t = doc.add_table(rows=0, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    t.autofit = False
    table_borders(t, LINE, 4)
    if header:
        r = t.add_row()
        cant_split(r)
        for i, htxt in enumerate(header):
            shade(r.cells[i], GREEN)
            cell_margins(r.cells[i])
            cell_text(r.cells[i], htxt, size=10.5, bold=True, color=CREAM, cn=CN_HEAD)
        repeat_header(r)
    for k, v in rows:
        r = t.add_row()
        cant_split(r)
        shade(r.cells[0], PAPER)
        cell_margins(r.cells[0])
        cell_margins(r.cells[1])
        cell_text(r.cells[0], k, size=10.5, bold=True, color=INK2, cn=CN_HEAD)
        cell_text(r.cells[1], v, size=10.5, color=INK)
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
    return t


def grid_table(doc, header, rows, widths, aligns=None, size=10, level_col=None):
    """level_col: 该列是等级词 → 用底纹单元格（不是胶囊，避免卡边）。"""
    t = doc.add_table(rows=1, cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    t.autofit = False
    table_borders(t, LINE, 4)
    hdr = t.rows[0]
    cant_split(hdr)
    for i, htxt in enumerate(header):
        shade(hdr.cells[i], GREEN)
        cell_margins(hdr.cells[i])
        cell_text(hdr.cells[i], htxt, size=size, bold=True, color=CREAM, cn=CN_HEAD,
                  align=(aligns[i] if aligns else "left"))
    repeat_header(hdr)
    for ri, row in enumerate(rows):
        r = t.add_row()
        cant_split(r)
        for i, val in enumerate(row):
            c = r.cells[i]
            cell_margins(c)
            al = aligns[i] if aligns else "left"
            if level_col is not None and i == level_col:
                shade(c, LV.get(val, PAPER))
                cell_text(c, val, size=size, bold=True, color=LV_INK.get(val, INK),
                          cn=CN_HEAD, align="center")
            else:
                if ri % 2 == 1:
                    shade(c, PAPER)
                cell_text(c, str(val), size=size, color=INK if al != "right" else INK,
                          align=al)
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
    return t


# ============================================================ 雷达图
def radar_svg(dims, W=560, H=430):
    """dims: [{short, pct}] —— 画**参考分布百分位**（票 #27 裁定，与产品内 HTML 版同口径）。

    为什么是百分位而不是正确率：
      - 正确率每维只有 5 题 → 取值只有 0/20/40/60/80/100 六个，形状很粗；
      - 参考环「中位 P50」「P25」只有在百分位口径下才成立（正确率口径下它就退化成
        普通刻度线，丢掉「参考分布中位」的语义）；
      - 正确数不丢：下面的维度表同时给出「对 / 总题数」与百分位、T 分，两个口径可互相推导。
    """
    cx, cy, R = W / 2.0, H / 2.0 + 4, 132
    n = len(dims)

    def pt(i, r):
        a = -math.pi / 2 + i * 2 * math.pi / n
        return (cx + math.cos(a) * r, cy + math.sin(a) * r)

    def poly(arr):
        return " ".join("%.1f,%.1f" % p for p in arr)

    out = []
    # 网格线（P25/P50/P75/P100 四个刻度位）；**不标刻度数字** —— 刻度数字标在顶部
    # 纵轴上会跟顶部维度的数值标签撞在一起，刻度含义写进图注。
    for f in (0.25, 0.5, 0.75, 1.0):
        out.append('<polygon points="%s" fill="none" stroke="#E6EAE7" stroke-width="1"/>'
                   % poly([pt(i, R * f) for i in range(n)]))
    # 参考环：P25 灰虚线、P50 金虚线（与产品内 HTML 版一致）
    out.append('<polygon points="%s" fill="none" stroke="#B7BEB9" stroke-width="1" '
               'stroke-dasharray="4 3"/>' % poly([pt(i, R * 0.25) for i in range(n)]))
    out.append('<polygon points="%s" fill="none" stroke="#C9A55C" stroke-width="1" '
               'stroke-dasharray="4 3"/>' % poly([pt(i, R * 0.5) for i in range(n)]))
    for i in range(n):
        p = pt(i, R)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#E6EAE7" '
                   'stroke-width="1"/>' % (cx, cy, p[0], p[1]))
    data = [pt(i, R * max(0.02, min(1.0, d["pct"] / 100.0))) for i, d in enumerate(dims)]
    out.append('<polygon points="%s" fill="#1E4634" fill-opacity="0.16" stroke="#1E4634" '
               'stroke-width="1.8"/>' % poly(data))
    for i, d in enumerate(dims):
        p = data[i]
        out.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="#1E4634"/>' % (p[0], p[1]))
        # 维度名放最外圈（r = R+34），数值沿半径外推到顶点外侧（r = 顶点 + 13）——
        # 两者在同一条半径上分开，绝不互相压字（第一版数值横着偏移、刻度数字标在
        # 顶部纵轴上，两处都会撞）。
        lp = pt(i, R + 34)
        out.append('<text x="%.1f" y="%.1f" font-size="11.5" fill="#16241C" '
                   'text-anchor="middle" font-family="%s">%s</text>'
                   % (lp[0], lp[1], RADAR_FONT, esc(d["short"])))
        # 水平轴上的两个顶点（左右两侧）：维度名很长、且沿半径向外推会落到名字底下，
        # 所以数值改放在顶点的**正上方**（图形内侧的空白处），与名字彻底分开。
        if abs(p[1] - cy) < 12:
            vx, vy, anchor = p[0], p[1] - 11, "middle"
        else:
            vr = math.hypot(p[0] - cx, p[1] - cy) + 13
            ang = math.atan2(p[1] - cy, p[0] - cx)
            vx, vy = cx + math.cos(ang) * vr, cy + math.sin(ang) * vr
            anchor = "start" if p[0] > cx + 6 else ("end" if p[0] < cx - 6 else "middle")
            vy += 4 if vy > cy else (-8 if vy < cy else 4)
        out.append('<text x="%.1f" y="%.1f" font-size="11" fill="#3C4B43" text-anchor="%s" '
                   'font-family="%s">P%d</text>' % (vx, vy, anchor, RADAR_FONT, d["pct"]))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d">%s</svg>' % (W, H, W, H, "".join(out)))


# 雷达图字体：与报告正文同一套系统栈（Apple 设备自动 SF Pro；不内嵌任何字体文件）
RADAR_FONT = "system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def svg_to_png(svg, path, scale=2):
    html = ('<!doctype html><html><head><meta charset="utf-8"><style>'
            'html,body{margin:0;padding:0;background:#fff}'
            'svg{display:block}</style></head><body>%s</body></html>' % svg)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        wp = f.name
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=%d" % scale,
                    "--window-size=560,430", "--screenshot=" + path, "file://" + wp],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    os.unlink(wp)
    return os.path.exists(path)


# ============================================================ 文档骨架
def setup_doc():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = EN_FONT
    st.font.size = Pt(10.5)
    st.font.color.rgb = RGBColor.from_string(INK)
    rf = st.element.rPr.rFonts
    rf.set(qn("w:eastAsia"), CN_FONT)
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.0)
    sec.left_margin, sec.right_margin = Cm(2.0), Cm(2.0)
    sec.header_distance, sec.footer_distance = Cm(1.2), Cm(1.0)
    return doc


def add_header_footer(doc, data):
    sec = doc.sections[0]
    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_fmt(hp.add_run("施测人报告 ｜ %s ｜ 编号 %s%s" % (
        data.get("name") or "—", (data.get("code") or "")[:18],
        (" ｜ 末4位 " + data["idLast4"]) if data.get("idLast4") else "")),
        size=8.5, color="5C6A60", cn=CN_FONT)
    pPr = hp._p.get_or_add_pPr()
    bdr = _el("w:pBdr")
    bdr.append(_el("w:bottom", val="single", sz="4", space="4", color=LINE))
    pPr.append(bdr)

    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for i, line in enumerate(FOOT_LINES):
        if i:
            fp.add_run().add_break()
        run_fmt(fp.add_run(line), size=8, color=SAND, cn=CN_FONT)
    p2 = sec.footer.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_fmt(p2.add_run("编号 %s ｜ 第 " % (data.get("code") or "—")), size=8,
            color="5C6A60", cn=CN_FONT)
    field(p2, " PAGE ")
    run_fmt(p2.add_run(" 页 / 共 "), size=8, color="5C6A60", cn=CN_FONT)
    field(p2, " NUMPAGES ")
    run_fmt(p2.add_run(" 页"), size=8, color="5C6A60", cn=CN_FONT)


def cover(doc, data, m1, m2, m3, compose):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    no_borders(t)
    c = t.rows[0].cells[0]
    shade(c, GREEN)
    cell_margins(c, top=200, left=220, bottom=200, right=220)
    c.text = ""
    p = c.paragraphs[0]
    p.paragraph_format.space_after = Pt(4)
    run_fmt(p.add_run("云上文旅集团 · 核心人才系列测试"), size=11, color=GOLD, cn=CN_HEAD)
    p2 = c.add_paragraph()
    p2.paragraph_format.space_after = Pt(2)
    run_fmt(p2.add_run("施测人报告"), size=26, bold=True, color=CREAM, cn=CN_HEAD)
    p3 = c.add_paragraph()
    p3.paragraph_format.space_after = Pt(0)
    run_fmt(p3.add_run("结果 · 解析 · 对候选人的判断"), size=11.5, color=CREAM, cn=CN_FONT)
    para(doc, "", after=10)

    rows = [
        ("候选人", data.get("name") or "—"),
        ("测评编号", data.get("code") or "—"),
        ("身份标识", ("末 4 位 " + data["idLast4"]) if data.get("idLast4") else "—"),
        ("报告日期", (data.get("date") or "")[:10] or "—"),
        ("报告性质", "内部判读材料：只产出追问清单，不作录用评分项"),
    ]
    kv_table(doc, rows, widths=(3.4, 11.8))

    para(doc, "", after=8)
    p = para(doc, "", after=6)
    run_fmt(p.add_run("综合评估　"), size=13, bold=True, color=GREEN, cn=CN_HEAD)
    run_fmt(p.add_run(compose["grade"]), size=13, bold=True, color=LV_INK.get(compose["grade"], INK),
            cn=CN_HEAD)
    run_fmt(p.add_run("　（三项等级等权合成，序数分 %.2f / 5）" % compose["score"]), size=10.5,
            color=INK2, cn=CN_FONT)

    kv_table(doc, [
        ("整体判断", compose.get("headline") or "见第三章「对候选人的判断」"),
        ("最短板", "%s（%s）" % (compose["short"]["name"], compose["short"]["grade"])),
        ("结构性偏科", "、".join("%s（%s）" % (i["name"], i["grade"]) for i in compose["skew"]) or "无"),
    ], widths=(3.4, 11.8))

    para(doc, "", after=6)
    para(doc, "本报告包含三章：第一章给结果（综合评估与三项明细），第二章逐项解读这个结果是怎么来的，"
              "第三章给对这位候选人的整体判断与面试追问方向。逐题回顾不在本报告范围内。",
         size=10.5, color=INK2, cn=CN_FONT, align="justify", after=4)


# ============================================================ 三章内容
def chapter_results(doc, data, m1, m2, m3, compose, radar_png):
    h1(doc, "结果", "一")
    h2(doc, "1.1　三项成绩")
    grid_table(doc,
               ["模块", "分数口径", "得分", "等级", "最短板维度"],
               [["第一项 · 管理行为成熟度", "四维 0–24 分（各维独立，无总档）", m1["score_text"], "无总档", m1["short_text"]],
                ["第二项 · 情境测试", "八维加权 0–5.00", "%.2f / 5.00" % m2["total"], m2["grade"], m2["short_text"]],
                ["第三项 · 推理测试", "难度加权 0–40 → 参考分布百分位", "%.1f 分 · P%s · T %s" % (
                    m3["total"], m3["pct"], m3["t"]), m3["grade"], m3["short_text"]]],
               widths=(4.6, 4.6, 3.4, 1.9, 3.0),
               aligns=["left", "left", "right", "center", "left"], level_col=3)
    para(doc, "", after=4)
    rich(doc, [("综合评估：", {"bold": True, "cn": CN_HEAD}),
               ("%s。综合评估由三项的等级合成（顶尖 5 / 优秀 4 / 良好 3 / 合格 2 / 待提升 1，"
                "等权平均后切档），不代表总分，也不是淘汰线，只用来决定面试追问什么。"
                % compose["grade"], {})], after=10)

    h2(doc, "1.2　第一项 · 管理行为成熟度（四维）")
    grid_table(doc, ["维度", "得分", "等级", "这一维在测什么"],
               [[d["name"], "%d / %d" % (d["score"], d["max"]), d["grade"], d["brief"]] for d in m1["dims"]],
               widths=(3.0, 2.2, 1.9, 10.4), aligns=["left", "right", "center", "left"], level_col=2)
    para(doc, "", after=4)
    rich(doc, [("短板维（四维里最弱的一维）：", {"bold": True, "cn": CN_HEAD}),
               ("%s。本项采用绝对锚点切档，尚未建立参照分布（内部样本到量后校准）。"
                % m1["short_text"], {})], after=10)

    h2(doc, "1.3　第二项 · 情境测试（八维）")
    grid_table(doc, ["维度", "归属", "权重", "得分", "等级", "需复核"],
               [[d["name"], d["outer_name"], "%d%%" % d["weight"], "%d / %d" % (d["score"], d["max"]),
                 d["grade"], "是" if d["flag"] else ""] for d in m2["dims"]],
               widths=(3.0, 2.8, 1.6, 2.0, 2.0, 1.8),
               aligns=["left", "left", "right", "right", "center", "center"], level_col=4)
    para(doc, "", after=4)
    rich(doc, [("加权总分 ", {}), ("%.2f / 5.00" % m2["total"], {"bold": True, "en": EN_FONT}),
               ("，等级 %s。" % m2["grade"], {})], after=4)
    if m2["consistency"]:
        para(doc, "一致性检查（同一致情境的两种问法是否指向同一倾向；不计入任何维度分）：",
             size=10.5, bold=True, color=INK2, cn=CN_HEAD, after=4)
        grid_table(doc, ["题对", "判定", "作答"], [[c["pair"], c["status"], c["detail"]] for c in m2["consistency"]],
                   widths=(2.6, 5.0, 9.9), aligns=["left", "left", "left"])
        para(doc, "", after=6)
    if m2["need_review"]:
        rich(doc, [("需复核：", {"bold": True, "cn": CN_HEAD}),
                   ("%s —— 自我参照与情境作答差异较大，按「需结合真实经历再确认」处理，不直接采信任一方。"
                    % "、".join(m2["need_review"]), {})], after=10)

    h2(doc, "1.4　第三项 · 推理测试（八维）")
    grid_table(doc, ["维度", "正确 / 总题", "正确率", "百分位", "T 分", "等级"],
               [[d["name"], "%d / %d" % (d["correct"], d["total"]), "%d%%" % d["rate"],
                 "P%s" % d["pct"], d["t"], d["grade"]] for d in m3["dims"]],
               widths=(3.2, 2.6, 2.2, 2.2, 2.0, 2.3),
               aligns=["left", "right", "right", "right", "right", "center"], level_col=5)
    para(doc, "", after=6)
    if radar_png and os.path.exists(radar_png):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(radar_png, width=Cm(12.6))
        para(doc, "第三项八维参考分布百分位（雷达几何刻度 = 百分位，与上表同口径；"
                  "金色虚线 = 中位 P50，灰色虚线 = P25，顶点数值为本次作答的百分位）",
             size=9, color=INK2, cn=CN_FONT, align="center", after=4)
    rich(doc, [("口径说明：", {"bold": True, "cn": CN_HEAD}),
               ("难度加权答对 %s 分，落在内置参考分布的第 %s 百分位、T 分 %s。"
                "百分位基于按题目难度加权的理论模型换算，不是商业常模，也不等同任何标准化智力测验；"
                "T 分超出 100 表示超出模型分布上端（满分作答的正常结果），档位以百分位为准。"
                % (m3["total"], m3["pct"], m3["t"]), {})], after=10)


def chapter_analysis(doc, m1, m2, m3, m1meta):
    h1(doc, "对结果的解析", "二")
    para(doc, "本章逐项说明上面的分数是怎么读出来的、各维度的判据是什么，以及哪些地方需要施测人结合其他材料再确认。",
         size=10.5, color=INK2, cn=CN_FONT, after=10)

    h2(doc, "2.1　第一项怎么读")
    para(doc, "第一项每一题是一道二极对比，两端都是行为频率陈述；每题锚定「更有效的一端」计 1 分，"
              "每维 0–24 分，只报四维各档、不合成总档；短板指四维里最弱的一维。下面逐维说明判据：",
         size=10.5, color=INK, cn=CN_FONT, align="justify", after=8)
    for d in m1["dims"]:
        meta = m1meta.get(d["key"], {})
        rich(doc, [("%s（%d / %d，%s）" % (d["name"], d["score"], d["max"], d["grade"]),
                    {"bold": True, "cn": CN_HEAD})], after=2)
        rich(doc, [("测什么：", {"bold": True, "color": INK2, "cn": CN_HEAD}),
                   (meta.get("definition", ""), {})], after=2, indent=0.6)
        rich(doc, [("判据：", {"bold": True, "color": INK2, "cn": CN_HEAD}),
                   (meta.get("behavior", ""), {})], after=2, indent=0.6)
        rich(doc, [("依据：", {"bold": True, "color": INK2, "cn": CN_HEAD}),
                   (meta.get("theory", ""), {})], after=8, indent=0.6)
    rich(doc, [("怎么用：", {"bold": True, "cn": CN_HEAD}),
               ("本项分数只说明工作方式上的倾向，不说明能力高低，也不诊断性格；"
                "短板那一维是面试最值得追问的方向。", {})], after=10)

    h2(doc, "2.2　第二项怎么读")
    para(doc, "第二项是八道管理情境维度上的行为反应：每维 6 道计分题（每题满分 2 分），"
              "按维度权重加权成 0–5.00，再切五档。分维等级如下：",
         size=10.5, color=INK, cn=CN_FONT, align="justify", after=6)
    grid_table(doc, ["维度", "得分", "等级", "判读口径"],
               [[d["name"], "%d / %d" % (d["score"], d["max"]), d["grade"], d["read"]] for d in m2["dims"]],
               widths=(3.0, 2.2, 2.0, 10.3), aligns=["left", "right", "center", "left"], level_col=2)
    para(doc, "", after=4)
    if m2["need_review"]:
        rich(doc, [("需要人工确认：", {"bold": True, "cn": CN_HEAD}),
                   ("%s。自我参照与情境作答差异偏大，说明候选人在「自己怎么描述自己」与"
                    "「当场怎么选」之间不一致——这本身是信息，面试时直接问这一维的具体场景，"
                    "不要在报告上替他下结论。" % "、".join(m2["need_review"]), {})], after=6)
    else:
        rich(doc, [("没有需要人工确认的维度。", {})], after=6)
    rich(doc, [("一致性检查读法：", {"bold": True, "cn": CN_HEAD}),
               ("同一情境的两种问法都选积极型或都选消极型，判为一致；一正一负判为需复核。"
                "一致性题不计入任何维度分，只用于观察倾向稳不稳。", {})], after=10)

    h2(doc, "2.3　第三项怎么读")
    para(doc, "第三项是陌生问题上的推理与判断：40 题按难度加权换算成百分位与 T 分，"
              "八个维度各自的正确率见下表。它测的是「面对没见过的规则怎么拆解」，"
              "与前两项不是同一件事。",
         size=10.5, color=INK, cn=CN_FONT, align="justify", after=8)
    for d in m3["dims"]:
        rich(doc, [("%s（%d / %d，%s）" % (d["name"], d["correct"], d["total"], d["grade"]),
                    {"bold": True, "cn": CN_HEAD})], after=2)
        if d.get("what"):
            rich(doc, [(d["what"], {})], after=2, indent=0.6)
        bits = []
        if d.get("high"):
            bits.append("表现好时：%s" % d["high"])
        if d.get("low"):
            bits.append("需要留意时：%s" % d["low"])
        if d.get("risk"):
            bits.append("常见风险：%s" % d["risk"])
        for b in bits:
            rich(doc, [(b, {})], after=2, indent=0.6)
        para(doc, "", after=6)
    rich(doc, [("怎么用：", {"bold": True, "cn": CN_HEAD}),
               ("第三项与前两项预期只有弱相关——如果两项分数高度同涨同跌，说明可能测的是同一件事，"
                "而不是候选人在多个方面都强，需要复核题目是否重叠。", {})], after=10)


def chapter_judgement(doc, compose, m1, m2, m3, m1meta):
    h1(doc, "对候选人的判断", "三")
    h2(doc, "3.1　整体判断")
    rich(doc, [("综合评估 %s。" % compose["grade"], {"bold": True, "cn": CN_HEAD, "size": 12}),
               ("三项等级等权合成（序数分 %.2f / 5），无总分。" % compose["score"], {"color": INK2})],
         after=6)
    for line in compose["paragraphs"]:
        rich(doc, [(line, {})], after=6, align="justify")
    if compose["skew"]:
        rich(doc, [("结构性偏科：", {"bold": True, "cn": CN_HEAD}),
                   ("综合档与 %s 相差 2 级以上，说明平均表现掩盖了单项塌陷，"
                    "应把该单项列为首要追问方向。"
                    % "、".join(i["name"] for i in compose["skew"]), {})], after=8)

    h2(doc, "3.2　面试追问清单")
    para(doc, "测评只产出追问清单，不作录用评分项。下列问题按短板与复核项生成，供面谈现场取证：",
         size=10.5, color=INK2, cn=CN_FONT, after=6)
    for i, q in enumerate(compose["questions"], 1):
        rich(doc, [("%d. " % i, {"bold": True, "color": GOLD, "en": EN_FONT, "size": 11}),
                   (q, {})], after=5, indent=0.5, align="justify")

    h2(doc, "3.3　使用边界")
    kv_table(doc, [
        ("结果性质", "只产出追问清单，不作录用评分项；同一岗位对所有候选人使用同一套题、同一权重、同一阈值。"),
        ("与面试冲突时", "以面试与工作样本为主，并记录冲突原因。"),
        ("不是淘汰线", "本产品不设淘汰线；综合评估与单项等级同样不产生淘汰动作。"),
        ("不做什么", "不测量性格，不测量智力，不属于临床心理评估，不对心理健康状况作判断。"),
        ("谁能看到", "集团人力资源部 2–3 名工作人员（含用人部门负责人），用于招聘环节的评估；不向其他人提供。"),
        ("留存与复核", "结果留在本机并由施测人归档；候选人如对结果有疑问，可在 5 个工作日内提出复核。"),
    ], widths=(3.4, 11.8))


# ============================================================ 组装
def build_context(data):
    """把结果 JSON + 题库合成报告需要的上下文。"""
    m1items = json.load(open(os.path.join(ROOT, "items", "m1_items.json"), encoding="utf-8"))
    m1meta = {d["key"]: d for d in m1items["meta"]["dimensions"]}
    eq = json.load(open(os.path.join(ROOT, "data", "eq_bank_encoded.json"), encoding="utf-8"))
    m3data = json.load(open(os.path.join(ROOT, "data", "logic_m3.json"), encoding="utf-8"))
    m3dims = m3data.get("dims", {})

    o = data["m1"]
    dims1 = []
    for d in o["dims"]:
        meta = m1meta.get(d["key"], {})
        brief = meta.get("definition", "")
        brief = brief.split("——")[0].split("是")[0][:38] if brief else ""
        dims1.append({"key": d["key"], "name": d["name"], "score": d["score"], "max": d["max"],
                       "grade": d["grade"], "brief": brief or meta.get("behavior", "")[:38]})
    # 第一项不给总档（ADR-0010）：不取 o["grade"]，只用短板维的档位；
    # 综合评估的第一项输入也取短板维档（数值与旧规则的总档完全相等 ⇒ 合成结果不变）。
    m1 = {"dims": dims1,
          "short": {"name": o["short"]["name"], "grade": o["short"]["grade"]},
          "short_text": "%s（%s）" % (o["short"]["name"], o["short"]["grade"]),
          "score_text": "四维 %s 分" % "、".join(str(d["score"]) for d in dims1)}

    o2 = data["m2"]
    wmap = {d["key"]: d for d in eq["dimensions"]}
    dims2 = []
    for d in o2["dims"]:
        w = wmap.get(d["key"], {})
        read = ("在该维度上的情境反应与自我参照基本一致。" if not d.get("flag")
                else "自我参照与情境作答差异偏大，此维结论待人工确认。")
        if d.get("selfAvg") is not None:
            read += "自我参照折算 %.2f / 5.00，与情境折算 %.2f / 5.00 %s。" % (
                d["selfAvg"], d["avg"], "差异 < 1.0" if not d.get("flag") else "差异 ≥ 1.0")
        dims2.append({"name": d["name"], "outer_name": w.get("outer_name", ""),
                       "weight": w.get("weight", 0), "score": d["score"], "max": d["max"],
                       "grade": d["grade"], "flag": d.get("flag"), "read": read})
    m2 = {"dims": dims2, "total": o2["total"], "grade": o2["grade"],
          "short_text": "%s（%s）" % (o2["short"]["name"], o2["short"]["grade"]),
          "need_review": o2.get("needReview", []),
          "consistency": o2.get("consistency", [])}

    o3 = data["m3"]
    dims3 = []
    for d in o3["dims"]:
        dm = m3dims.get(d["key"], {})
        dims3.append({"key": d["key"], "name": d["name"], "short": dm.get("short", d["name"]),
                       "correct": d["correct"], "total": d["total"], "rate": d["rate"],
                       "pct": d["pct"], "t": d["t"], "grade": d["grade"],
                       "what": dm.get("what", ""), "high": dm.get("high", ""),
                       "low": dm.get("low", ""), "job": dm.get("job", ""),
                       "risk": dm.get("risk", "")})
    # 注意：产品 resultObj() 里 m3.out 不含 short（short 只在 score() 的外层对象上），
    # 这里按等级序数从 dims 里自己取最低维，口径与 report.js 的短板规则一致。
    short3 = sorted(dims3, key=lambda d: ORDER.index(d["grade"]) if d["grade"] in ORDER else 0)[0]
    m3 = {"dims": dims3, "total": o3["total"], "pct": o3["pct"], "t": o3["t"], "grade": o3["grade"],
          "short_text": "%s（%s）" % (short3["name"], short3["grade"])}

    # 结果 JSON（产品 resultObj()）里**没有 compose** —— 那是 REP.build() 现场算的。
    # 这里按 report.js 的合成规则自己算，口径必须一致：
    # 序数分（顶尖5/优秀4/良好3/合格2/待提升1）等权平均 → bandComposite 切档；
    # 短板 = 三项里等级最低的那一项；结构性偏科 = 与综合档相差 ≥2 级的项。
    def band_composite(v):
        return ("顶尖" if v >= 4.5 else "优秀" if v >= 3.75 else "良好" if v >= 3.0
                else "合格" if v >= 2.25 else "待提升")

    items = [{"name": "第一项 · " + m1items["meta"]["title"], "grade": m1["short"]["grade"]},
             {"name": "第二项 · 情境测试", "grade": m2["grade"]},
             {"name": "第三项 · 推理测试", "grade": m3["grade"]}]
    avg = sum(ORDER.index(i["grade"]) for i in items) / 3.0
    cgrade = band_composite(avg)
    cshort = sorted(items, key=lambda i: ORDER.index(i["grade"]))[0]
    compose = {
        "grade": cgrade, "score": round(avg, 2),
        "short": {"name": cshort["name"], "grade": cshort["grade"]},
        "skew": [i for i in items if ORDER.index(cgrade) - ORDER.index(i["grade"]) >= 2],
        "headline": "", "paragraphs": [], "questions": [],
    }
    return m1, m2, m3, compose, m1meta


def compose_text(compose, m1, m2, m3, m1meta):
    """把三项结果与综合评估写成「对候选人的判断」与追问清单。"""
    grade = compose["grade"]
    short = compose["short"]
    # 维度级短板：第一项内部最低的那一维（模块级短板是「第一项/第二项/第三项」之一）
    short_dim = min(m1["dims"], key=lambda d: ORDER.index(d["grade"]) if d["grade"] in ORDER else 9)
    sk = m1meta.get(short_dim["key"], {})
    paras = []
    paras.append(
        "这位候选人三项的综合评估为%s。综合评估是三项等级（顶尖 5 / 优秀 4 / 良好 3 / 合格 2 / "
        "待提升 1）等权平均后切的档，不产生总分，也不是任何形式的淘汰线。" % grade)
    paras.append(
        "三项里最弱的是%s（%s）；第一项（行为倾向）不合成总档，最弱的一维在「%s」（%s）——"
        "这一维更值得在面试里展开：%s"
        % (short.get("name", "—"), short.get("grade", "—"),
           short_dim["name"], short_dim["grade"],
           (sk.get("behavior", "") or "结合具体工作场景核实其真实工作顺序。")))
    paras.append(
        "第二项（情境反应）加权 %.2f / 5.00，等级%s；%s第三项（推理与判断）落在参考分布第 %s 百分位"
        "（T 分 %s），等级%s。%s"
        % (m2["total"], m2["grade"],
           ("其中 %s 需人工确认。" % "、".join(m2["need_review"])) if m2["need_review"] else "",
           m3["pct"], m3["t"], m3["grade"],
           "第三项与前两项预期弱相关，同涨同跌时应复核题目是否重叠，而不是直接加分。"))
    paras.append(
        "结论口径：以上只说明这位候选人在常规工作方式、具体管理情境、陌生问题推理三个切面上的表现倾向，"
        "不说明能力高低，不诊断性格，也不作录用评分项。录用决策应由简历、专业技能、面谈与工作样本"
        "等多源证据支撑；测评与面试冲突时以面试与工作样本为主，并记录冲突原因。")

    qs = []
    qs.append("围绕第一项的短板「%s」：请他复盘一个最近三个月里，%s的具体场景——当时怎么做的、"
              "为什么这么排、代价是什么。" % (short_dim["name"],
                                            (sk.get("behavior", "") or "该维度判据").split("；")[0][:46]))
    if m2["need_review"]:
        qs.append("第二项里 %s 这几维，他的自我描述和现场选择不一致：请他给一个真实案例，"
                  "看两种答案各自对应什么处境。" % "、".join(m2["need_review"]))
    need = [c for c in m2["consistency"] if "需复核" in c.get("status", "")]
    if need:
        qs.append("第二项一致性检查里 %s 这几对同一情境选了不同方向：说明倾向在两可情境下不稳定，"
                  "请他说明两种情境各自发生了什么。" % "、".join(c["pair"] for c in need))
    for s in compose["skew"]:
        qs.append("%s 这一项与综合评估相差 2 级以上（结构性偏科）：请他描述一次该维度明显拖后腿的经历，"
                  "以及后来怎么调整。" % s["name"])
    m3low = sorted(m3["dims"], key=lambda d: d["rate"])[:1]
    if m3low:
        d = m3low[0]
        qs.append("第三项里「%s」正确率 %d%%（八维中最低）：请他讲一道当时判断错的题，"
                  "看他复盘时会不会改结论、还是为原答案找理由。" % (d["name"], d["rate"]))
    qs.append("对照他简历上的最近一段经历，请他讲一个「本来可以更早发现、但没有」的问题，"
              "看他是先复盘事实还是先归因（对应第一项「关注重点」）。")
    compose["paragraphs"] = paras
    compose["questions"] = qs
    compose["headline"] = "%s；最短板：%s（%s）" % (grade, short.get("name", "—"), short.get("grade", "—"))
    return compose


# ============================================================ HTML 双胞胎
# 与 Word 版同源同数：数据、判读文字、追问清单都来自同一批函数，只有排版分开。
# 产出自包含单文件（样式内联、雷达图 base64 内联、零外链），供 Chrome 打印成 PDF。
HTML_CSS = """
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:"Songti SC","Source Han Serif SC",Georgia,serif;color:#1D2A23;
  font-size:10.5pt;line-height:1.62;-webkit-print-color-adjust:exact;print-color-adjust:exact;
  padding-top:11mm;padding-bottom:14mm}   /* 给跑头/跑尾留安全带，正文不与之重叠 */
h1,h2,.head,.band,.tbl th{font-family:"Heiti SC","Source Han Sans SC","PingFang SC",sans-serif}
.num{font-family:Georgia,"Times New Roman",serif;font-variant-numeric:tabular-nums}

/* 页码与合规页脚都走 @page margin box（Chrome ≥131 支持；Firefox/Safari 忽略 → 降级为无页脚）。
   为什么不用 position:fixed：fixed 元素定位基准是内容盒，负偏移在第一页会被裁掉，
   正偏移则会在**满页时压在正文上**（踩过：最后一行表格被页脚盖住）。
   margin box 在内容区之外，物理上不可能重叠。 */
@page{
  size:A4; margin:16mm 18mm 20mm 20mm;
  /* 左盒每行宽度必须留出右盒的位置：左盒太宽会把右盒挤窄 → 页码折行（踩过：
     「第 6 页 / 共 10」被折成两行）。所以左盒每行 ≤ ~55mm，右盒页码用紧凑写法。 */
  @bottom-left{content:"本报告由本地单文件测评结果生成，不上传服务器\A不得作为录用唯一依据；不构成医学或心理诊断；不设淘汰线";
    font-family:"Songti SC",serif;font-size:7pt;color:#6E5B36;line-height:1.4;vertical-align:bottom}
  @bottom-right{content:"第 " counter(page) " / " counter(pages) " 页";
    font-family:Georgia,serif;font-size:8pt;color:#5C6A60;vertical-align:bottom}
}
/* 跑头（候选人身份）：仍在内容盒内，靠 body 上边距让开正文 */
.runhead{position:fixed;top:0;left:20mm;right:18mm;text-align:right;font-size:8pt;color:#5C6A60;
  padding-bottom:2px;border-bottom:.5px solid #E6EAE7}
.tailnote{font-size:7.5pt;color:#6E5B36;line-height:1.5;margin-top:6mm;
  border-top:.5px solid #E6EAE7;padding-top:2mm}

.cover{background:#1E4634;color:#F5F0E4;padding:10mm 9mm;margin-bottom:6mm}
.cover .brand{color:#C9A55C;font-size:9.5pt;letter-spacing:.5px}
.cover .title{font-size:26pt;font-weight:700;margin:2mm 0 1mm}
.cover .sub{font-size:10.5pt;opacity:.92}

.kv{width:100%;border-collapse:collapse;margin:0 0 5mm}
.kv td{border:.5px solid #E6EAE7;padding:2.2mm 3mm;vertical-align:top}
.kv td.k{width:26mm;background:#FAF9F4;font-weight:700;color:#42544B;font-family:"Heiti SC",sans-serif}

h1{font-size:16pt;color:#1E4634;margin:0 0 2mm;padding-bottom:1.5mm;
  border-bottom:1.2px solid #C9A55C;break-after:avoid}
h2{font-size:12pt;color:#1E4634;margin:5mm 0 2mm;break-after:avoid}
p{margin:0 0 2.2mm}
.sec{break-before:page}
.lead{color:#42544B;margin-bottom:4mm}
.note{font-size:9.5pt;color:#42544B}

.tbl{width:100%;border-collapse:collapse;margin:2mm 0 4mm;font-size:10pt}
.tbl th{background:#1E4634;color:#F5F0E4;text-align:left;padding:1.8mm 2.4mm;font-weight:700}
.tbl td{border:.5px solid #E6EAE7;padding:1.8mm 2.4mm;vertical-align:top}
.tbl tr{break-inside:avoid}
.tbl tbody tr:nth-child(even) td{background:#FAF9F4}
.tbl td.r,.tbl th.r{text-align:right}
.tbl td.c,.tbl th.c{text-align:center}
.lv{display:inline-block;padding:1px 8px;border-radius:6px;font-family:"Heiti SC",sans-serif;
  font-weight:700;font-size:9.5pt;white-space:nowrap}
/* 等级标签用底纹 + 足够内边距：padding ≥ 圆角半径，字不会卡在圆弧里 */
.lv-T{background:#E5F1EB;color:#1B7A56}.lv-A{background:#E5F1EB;color:#1B7A56}
.lv-B{background:#EFF1EF;color:#2A5C42}.lv-C{background:#F4EEE0;color:#6E5B36}
.lv-D{background:#FBEDEA;color:#8E2F26}

.callout{background:#F5F0E4;border-left:2.4px solid #C9A55C;padding:2.6mm 3.4mm;margin:3mm 0}
.dim h3{font-size:10.5pt;margin:3mm 0 1mm;color:#1E4634;break-after:avoid}
.dim dl{margin:0 0 0 4mm}
.dim dt{font-size:9.5pt;color:#42544B;font-family:"Heiti SC",sans-serif;float:left;clear:left;
  width:14mm}
.dim dd{margin:0 0 1mm 16mm}
.qs{counter-reset:q}
.qs li{margin:0 0 2mm 5mm}
.radar{text-align:center;margin:3mm 0}
.radar img{width:126mm}
.cap{font-size:9pt;color:#42544B;text-align:center}
"""


# ============================================================ 视觉模板
# 视觉与排版走 src/report_template.css —— 按 Apple HIG → Web 规范写的模板
# （字阶、语义色、4/8 间距节奏、深色模式、打印样式；依据与检查表见该文件头）。
# 旧的内联 CSS 保留在 HTML_CSS 里作对照，勿再往里加规则。
TEMPLATE_CSS_PATH = os.path.join(ROOT, "src", "report_template.css")


def template_css(runhead=""):
    """读视觉模板，并把跑头文案填进 @page 的 @top-right（每页都带身份，且不压正文）。"""
    with open(TEMPLATE_CSS_PATH, encoding="utf-8") as f:
        css = f.read()
    safe = str(runhead).replace("\\", "\\\\").replace('"', '\\"')
    return css.replace("__RUNHEAD__", safe)


def lv_class(grade):
    # 「无总档」（第一项，ADR-0010）不是一个等级，不套等级色
    if grade in ("无总档", "—", ""):
        return ""
    return {"顶尖": "lv-T", "优秀": "lv-A", "良好": "lv-B", "合格": "lv-C", "待提升": "lv-D"}.get(grade, "lv-B")


def h(s):
    return esc(s)


def render_html(data, m1, m2, m3, compose, m1meta, radar_png):
    import base64
    radar_b64 = ""
    if radar_png and os.path.exists(radar_png):
        with open(radar_png, "rb") as f:
            radar_b64 = base64.b64encode(f.read()).decode("ascii")

    o = []
    A = o.append
    A("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">")
    A("<title>施测人报告 · %s</title>" % h(data.get("name") or ""))
    runhead = "施测人报告 ｜ %s ｜ 编号 %s%s" % (
        h(data.get("name") or "—"), h((data.get("code") or "")[:18]),
        (" ｜ 末4位 " + h(data["idLast4"])) if data.get("idLast4") else "")
    A("<style>%s</style></head><body>" % template_css(runhead))
    A('<div class="runhead">%s</div>' % runhead)

    # ---------------- 封面
    A('<div class="cover"><div class="brand">云上文旅集团 · 核心人才系列测试</div>'
      '<div class="title">施测人报告</div>'
      '<div class="sub">结果 · 解析 · 对候选人的判断</div></div>')
    A('<table class="kv">')
    for k, v in (("候选人", data.get("name") or "—"),
                 ("测评编号", data.get("code") or "—"),
                 ("身份标识", ("末 4 位 " + data["idLast4"]) if data.get("idLast4") else "—"),
                 ("报告日期", (data.get("date") or "")[:10] or "—"),
                 ("报告性质", "内部判读材料：只产出追问清单，不作录用评分项")):
        A('<tr><td class="k">%s</td><td>%s</td></tr>' % (h(k), h(v)))
    A("</table>")
    A('<p><b>综合评估</b> <span class="lv %s">%s</span>'
      '<span class="note">（三项等级等权合成，序数分 %.2f / 5）</span></p>'
      % (lv_class(compose["grade"]), h(compose["grade"]), compose["score"]))
    A('<table class="kv">')
    for k, v in (("整体判断", compose["headline"]),
                 ("最短板", "%s（%s）" % (compose["short"]["name"], compose["short"]["grade"])),
                 ("结构性偏科", "、".join("%s（%s）" % (i["name"], i["grade"]) for i in compose["skew"]) or "无")):
        A('<tr><td class="k">%s</td><td>%s</td></tr>' % (h(k), h(v)))
    A("</table>")
    A('<p class="note">本报告包含三章：第一章给结果（综合评估与三项明细），第二章逐项解读这个结果是怎么来的，'
      '第三章给对这位候选人的整体判断与面试追问方向。逐题回顾不在本报告范围内。</p>')

    # ---------------- 一、结果
    A('<div class="sec"><h1>一、结果</h1>')
    A('<h2>1.1　三项成绩</h2>')
    A('<table class="tbl"><thead><tr><th>模块</th><th>分数口径</th><th class="r">得分</th>'
      '<th class="c">等级</th><th>最短板维度</th></tr></thead><tbody>')
    for row in (["第一项 · 管理行为成熟度", "四维 0–24 分（各维独立，无总档）", m1["score_text"], "无总档", m1["short_text"]],
                ["第二项 · 情境测试", "八维加权 0–5.00", "%.2f / 5.00" % m2["total"], m2["grade"], m2["short_text"]],
                ["第三项 · 推理测试", "难度加权 0–40 → 参考分布百分位",
                 "%.1f 分 · P%s · T %s" % (m3["total"], m3["pct"], m3["t"]), m3["grade"], m3["short_text"]]):
        A('<tr><td>%s</td><td>%s</td><td class="r num">%s</td><td class="c">'
          '<span class="lv %s">%s</span></td><td>%s</td></tr>'
          % (h(row[0]), h(row[1]), h(row[2]), lv_class(row[3]), h(row[3]), h(row[4])))
    A("</tbody></table>")
    A('<p>综合评估 <b>%s</b>。综合评估由三项的等级合成（顶尖 5 / 优秀 4 / 良好 3 / 合格 2 / 待提升 1，'
      '等权平均后切档），不代表总分，也不是淘汰线，只用来决定面试追问什么。</p>' % h(compose["grade"]))

    A('<h2>1.2　第一项 · 管理行为成熟度（四维）</h2>')
    A('<table class="tbl"><thead><tr><th>维度</th><th class="r">得分</th><th class="c">等级</th>'
      '<th>这一维在测什么</th></tr></thead><tbody>')
    for d in m1["dims"]:
        A('<tr><td>%s</td><td class="r num">%d / %d</td><td class="c"><span class="lv %s">%s</span></td>'
          '<td>%s</td></tr>' % (h(d["name"]), d["score"], d["max"], lv_class(d["grade"]),
                               h(d["grade"]), h(d["brief"])))
    A("</tbody></table>")
    A('<p>短板维（四维里最弱的一维）：<b>%s</b>。本项采用绝对锚点切档，尚未建立参照分布'
      '（内部样本到量后校准）。</p>' % h(m1["short_text"]))

    A('<h2>1.3　第二项 · 情境测试（八维）</h2>')
    A('<table class="tbl"><thead><tr><th>维度</th><th>归属</th><th class="r">权重</th>'
      '<th class="r">得分</th><th class="c">等级</th><th class="c">需复核</th></tr></thead><tbody>')
    for d in m2["dims"]:
        A('<tr><td>%s</td><td>%s</td><td class="r num">%d%%</td><td class="r num">%d / %d</td>'
          '<td class="c"><span class="lv %s">%s</span></td><td class="c">%s</td></tr>'
          % (h(d["name"]), h(d["outer_name"]), d["weight"], d["score"], d["max"],
             lv_class(d["grade"]), h(d["grade"]), ("是" if d["flag"] else "")))
    A("</tbody></table>")
    A('<p>加权总分 <b class="num">%.2f / 5.00</b>，等级 %s。</p>' % (m2["total"], h(m2["grade"])))
    if m2["consistency"]:
        A('<p><b>一致性检查</b>（同一致情境的两种问法是否指向同一倾向；不计入任何维度分）</p>')
        A('<table class="tbl"><thead><tr><th>题对</th><th>判定</th><th>作答</th></tr></thead><tbody>')
        for c in m2["consistency"]:
            A('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (h(c["pair"]), h(c["status"]), h(c["detail"])))
        A("</tbody></table>")
    if m2["need_review"]:
        A('<div class="callout">需复核：<b>%s</b> —— 自我参照与情境作答差异较大，'
          '按「需结合真实经历再确认」处理，不直接采信任一方。</div>' % h("、".join(m2["need_review"])))

    A('<h2>1.4　第三项 · 推理测试（八维）</h2>')
    A('<table class="tbl"><thead><tr><th>维度</th><th class="r">正确 / 总题</th><th class="r">正确率</th>'
      '<th class="r">百分位</th><th class="r">T 分</th><th class="c">等级</th></tr></thead><tbody>')
    for d in m3["dims"]:
        A('<tr><td>%s</td><td class="r num">%d / %d</td><td class="r num">%d%%</td>'
          '<td class="r num">P%s</td><td class="r num">%s</td><td class="c">'
          '<span class="lv %s">%s</span></td></tr>'
          % (h(d["name"]), d["correct"], d["total"], d["rate"], d["pct"], h(d["t"]),
             lv_class(d["grade"]), h(d["grade"])))
    A("</tbody></table>")
    if radar_b64:
        A('<div class="radar"><img src="data:image/png;base64,%s" alt="第三项八维百分位雷达图"></div>' % radar_b64)
        A('<p class="cap">第三项八维参考分布百分位（雷达几何刻度 = 百分位，与上表同口径；金色虚线 = 中位 P50，灰色虚线 = P25，顶点数值为本次作答的百分位）</p>')
    A('<p><b>口径说明：</b>难度加权答对 %s 分，落在内置参考分布的第 %s 百分位、T 分 %s。'
      '百分位基于按题目难度加权的理论模型换算，不是商业常模，也不等同任何标准化智力测验；'
      'T 分超出 100 表示超出模型分布上端（满分作答的正常结果），档位以百分位为准。</p>'
      % (h(str(m3["total"])), h(str(m3["pct"])), h(str(m3["t"]))))
    A("</div>")

    # ---------------- 二、解析
    A('<div class="sec"><h1>二、对结果的解析</h1>')
    A('<p class="lead">本章逐项说明上面的分数是怎么读出来的、各维度的判据是什么，'
      '以及哪些地方需要施测人结合其他材料再确认。</p>')
    A('<h2>2.1　第一项怎么读</h2>')
    A('<p>第一项每一题是一道二极对比，两端都是行为频率陈述；每题锚定「更有效的一端」计 1 分，'
      '每维 0–24 分，只报四维各档、不合成总档；短板指四维里最弱的一维。下面逐维说明判据：</p>')
    for d in m1["dims"]:
        meta = m1meta.get(d["key"], {})
        A('<div class="dim"><h3>%s（%d / %d，%s）</h3><dl>'
          '<dt>测什么</dt><dd>%s</dd><dt>判据</dt><dd>%s</dd><dt>依据</dt><dd>%s</dd></dl></div>'
          % (h(d["name"]), d["score"], d["max"], h(d["grade"]), h(meta.get("definition", "")),
             h(meta.get("behavior", "")), h(meta.get("theory", ""))))
    A('<p><b>怎么用：</b>本项分数只说明工作方式上的倾向，不说明能力高低，也不诊断性格；'
      '短板那一维是面试最值得追问的方向。</p>')

    A('<h2>2.2　第二项怎么读</h2>')
    A('<p>第二项是八道管理情境维度上的行为反应：每维 6 道计分题（每题满分 2 分），'
      '按维度权重加权成 0–5.00，再切五档。分维等级如下：</p>')
    A('<table class="tbl"><thead><tr><th>维度</th><th class="r">得分</th><th class="c">等级</th>'
      '<th>判读口径</th></tr></thead><tbody>')
    for d in m2["dims"]:
        A('<tr><td>%s</td><td class="r num">%d / %d</td><td class="c"><span class="lv %s">%s</span></td>'
          '<td>%s</td></tr>' % (h(d["name"]), d["score"], d["max"], lv_class(d["grade"]),
                               h(d["grade"]), h(d["read"])))
    A("</tbody></table>")
    if m2["need_review"]:
        A('<p><b>需要人工确认：</b>%s。自我参照与情境作答差异偏大，说明候选人在「自己怎么描述自己」与'
          '「当场怎么选」之间不一致——这本身是信息，面试时直接问这一维的具体场景，不要在报告上替他下结论。</p>'
          % h("、".join(m2["need_review"])))
    else:
        A("<p>没有需要人工确认的维度。</p>")
    A('<p><b>一致性检查读法：</b>同一情境的两种问法都选积极型或都选消极型，判为一致；一正一负判为需复核。'
      '一致性题不计入任何维度分，只用于观察倾向稳不稳。</p>')

    A('<h2>2.3　第三项怎么读</h2>')
    A('<p>第三项是陌生问题上的推理与判断：40 题按难度加权换算成百分位与 T 分，'
      '八个维度各自的正确率见下表。它测的是「面对没见过的规则怎么拆解」，与前两项不是同一件事。</p>')
    for d in m3["dims"]:
        A('<div class="dim"><h3>%s（%d / %d，%s）</h3><dl>'
          '<dt>在测</dt><dd>%s</dd>' % (h(d["name"]), d["correct"], d["total"], h(d["grade"]), h(d.get("what", ""))))
        if d.get("high"):
            A('<dt>表现好时</dt><dd>%s</dd>' % h(d["high"]))
        if d.get("low"):
            A('<dt>需要留意时</dt><dd>%s</dd>' % h(d["low"]))
        if d.get("risk"):
            A('<dt>常见风险</dt><dd>%s</dd>' % h(d["risk"]))
        A("</dl></div>")
    A('<p><b>怎么用：</b>第三项与前两项预期只有弱相关——如果两项分数高度同涨同跌，'
      '说明可能测的是同一件事，而不是候选人在多个方面都强，需要复核题目是否重叠。</p>')
    A("</div>")

    # ---------------- 三、判断
    A('<div class="sec"><h1>三、对候选人的判断</h1>')
    A('<h2>3.1　整体判断</h2>')
    A('<p><b>综合评估 %s。</b><span class="note">三项等级等权合成（序数分 %.2f / 5），无总分。</span></p>'
      % (h(compose["grade"]), compose["score"]))
    for line in compose["paragraphs"]:
        A("<p>%s</p>" % h(line))
    if compose["skew"]:
        A('<div class="callout"><b>结构性偏科：</b>综合档与 %s 相差 2 级以上，'
          '说明平均表现掩盖了单项塌陷，应把该单项列为首要追问方向。</div>'
          % h("、".join(i["name"] for i in compose["skew"])))
    A('<h2>3.2　面试追问清单</h2>')
    A('<p class="lead">测评只产出追问清单，不作录用评分项。下列问题按短板与复核项生成，供面谈现场取证：</p>')
    A('<ol class="qs">')
    for q in compose["questions"]:
        A("<li>%s</li>" % h(q))
    A("</ol>")
    A('<h2>3.3　使用边界</h2>')
    A('<table class="kv">')
    for k, v in (("结果性质", "只产出追问清单，不作录用评分项；同一岗位对所有候选人使用同一套题、同一权重、同一阈值。"),
                 ("与面试冲突时", "以面试与工作样本为主，并记录冲突原因。"),
                 ("不是淘汰线", "本产品不设淘汰线；综合评估与单项等级同样不产生淘汰动作。"),
                 ("不做什么", "不测量性格，不测量智力，不属于临床心理评估，不对心理健康状况作判断。"),
                 ("谁能看到", "集团人力资源部 2–3 名工作人员（含用人部门负责人），用于招聘环节的评估；不向其他人提供。"),
                 ("留存与复核", "结果留在本机并由施测人归档；候选人如对结果有疑问，可在 5 个工作日内提出复核。")):
        A('<tr><td class="k">%s</td><td>%s</td></tr>' % (h(k), h(v)))
    A("</table></div>")

    # 文末落款：完整的合规页脚原文（每页页脚带的是压缩版，完整版在这里留底）
    A('<div class="tailnote">')
    for line in FOOT_LINES:
        A(h(line) + "<br>")
    A('编号 %s ｜ 末 4 位 %s</div>' % (h(data.get("code") or "—"), h(data.get("idLast4") or "—")))

    A("</body></html>")
    return "".join(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(ROOT, "pilot", "out", "模拟试测_结果JSON_样例.json"))
    ap.add_argument("--outdir", default=OUTDIR)
    args = ap.parse_args()

    data = json.load(open(args.json, encoding="utf-8"))
    m1, m2, m3, compose, m1meta = build_context(data)
    compose = compose_text(compose, m1, m2, m3, m1meta)

    os.makedirs(args.outdir, exist_ok=True)
    code = (data.get("code") or "REPORT").replace("/", "-")
    stamp = (data.get("date") or "")[:10].replace("-", "") or "00000000"
    base = "施测人报告_%s_%s" % (code, stamp)
    docx_path = os.path.join(args.outdir, base + ".docx")

    # 雷达图 → PNG
    radar_png = None
    try:
        svg = radar_svg([{"short": d["short"], "pct": d["pct"]} for d in m3["dims"]])
        cand = os.path.join(args.outdir, base + "_第三项雷达图.png")
        if svg_to_png(svg, cand, scale=2):
            radar_png = cand
            print("雷达图：%s" % os.path.basename(cand))
    except Exception as e:  # 雷达图失败不阻塞报告
        print("雷达图生成失败（不影响报告）：%s" % e)

    doc = setup_doc()
    add_header_footer(doc, data)
    cover(doc, data, m1, m2, m3, compose)
    page_break(doc)
    chapter_results(doc, data, m1, m2, m3, compose, radar_png)
    page_break(doc)
    chapter_analysis(doc, m1, m2, m3, m1meta)
    page_break(doc)
    chapter_judgement(doc, compose, m1, m2, m3, m1meta)
    doc.save(docx_path)
    print("Word：%s" % docx_path)

    # Word → PDF：**不能走 LibreOffice**。本机 LibreOffice 26.8 没有可用中文字体
    # （连 HTML→PDF 都回退到希伯来字体），导出的 PDF 全是豆腐块；.docx 本身没问题，
    # Word/Pages 有中文字体。PDF 改由 Chrome 打印 HTML 双胞胎（Chrome 的中文渲染没问题）。
    html_path = os.path.join(args.outdir, base + ".html")
    html = render_html(data, m1, m2, m3, compose, m1meta, radar_png)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML：%s（单文件 · 零外链）" % html_path)

    pdf_path = docx_path[:-5] + ".pdf"
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--virtual-time-budget=8000", "--print-to-pdf=" + pdf_path,
                        "file://" + html_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    if os.path.exists(pdf_path):
        print("PDF ：%s（%.1f KB）" % (pdf_path, os.path.getsize(pdf_path) / 1024))
    else:
        print("PDF 生成失败")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
