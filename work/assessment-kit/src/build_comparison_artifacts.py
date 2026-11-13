#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核心人才三联测试 · 三人衍生产物生成器（对比总表 / 苹果风长图 / 汇总封面）

这三份 HTML 原来是在编辑器里手写的：数字从单份报告里抄过来，判读文字当场写，
样式当场调。2026-10-26 之前它们没有仓内生成脚本 —— 产物进了仓、逻辑没进仓，
于是「定稿不可复现 = 不可维护」（票 #79）。

本脚本把这三份产物变成**可重建**的：

  输入  src/comparison_spec.json
        · 分数：与三份单份报告同源（pilot/out/结果JSON_*.json）
          —— 本脚本的 --cross-check 只在结果 JSON 存在时才有意义：找不到就打印
          「跳过」并正常退出（生成器是生成器，不是门）。
          **门**是 src/verify_report_artifacts.py：它自己做这份核对，
          且结果 JSON 缺失即判红（新克隆/CI 上 pilot/out 是 gitignore 的，
          跳过就等于永远绿）。
        · 判读文字：人工撰写、无法自动再生，只能在 spec 里维护（脚本只装配，不改写）
          —— 哪些值没有机器来源、人工依据是什么，见 spec 的 "no_source" 清单
  计算  百分比、档位（≥85 突出 / 70–85 常规 / <70 偏弱）、类型归类、形象类比
        —— 全部走 src/report_v2_profile.py，档位口径与单份报告共用同一处实现
  输出  三份 HTML（版式与已提交产物逐字节一致）

用法：
    python3 src/build_comparison_artifacts.py --outdir <目录>
    python3 src/build_comparison_artifacts.py --outdir <目录> --cross-check
    python3 src/build_comparison_artifacts.py --outdir reports/ --overwrite

约束：无第三方依赖、无网络。--outdir 默认写 reports/，但目标文件已存在且内容不同时
拒绝写入（要覆盖必须显式 --overwrite），避免手滑冲掉已定稿的产物。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_SPEC = os.path.join(HERE, "comparison_spec.json")
DEFAULT_OUTDIR = os.path.join(ROOT, "reports")

sys.path.insert(0, HERE)
import report_v2_profile as RVP  # noqa: E402  档位/类型/形象类比的口径唯一出处

# ── 产物文件名（与已提交产物同名；改动会让断言失败）────────────────────────────
F_COVER = "核心人才三联测试_汇总封面_%s.html"
F_TABLE = "三人核心人才三联测试_对比总表_%s.html"
F_LONG = "三人核心人才三联测试_苹果风长图_%s.html"

# ── 版式常量：直接取自已提交产物，逐字节保真 ─────────────────────────────────
CSS_COVER = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f5f0e4; padding: 40px; }
  .wrap { max-width: 1000px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 48px; box-shadow: 0 2px 12px rgba(30,70,52,0.1); }
  .brand { font-size: 11px; color: #B08D57; letter-spacing: 0.1em; margin-bottom: 4px; }
  h1 { font-size: 26px; font-weight: 700; color: #1E4634; margin-bottom: 6px; }
  .subtitle { font-size: 13px; color: #6E5B36; margin-bottom: 30px; }
  .org-block { background: #EEF3EE; border-left: 4px solid #1E4634; padding: 14px 18px; margin-bottom: 30px; border-radius: 0 8px 8px 0; }
  .org-label { font-size: 11px; color: #6E5B36; margin-bottom: 4px; letter-spacing: 0.05em; }
  .org-name { font-size: 16px; font-weight: 600; color: #1E4634; }
  .section-title { font-size: 14px; font-weight: 700; color: #1E4634; margin: 24px 0 10px; padding-bottom: 4px; border-bottom: 2px solid #B08D57; }
  table { width: 100%; border-collapse: collapse; }
  th, td { border: 1px solid #d9d2c2; padding: 10px 12px; font-size: 13px; text-align: left; }
  th { background: #1E4634; color: #F5F0E4; font-weight: 600; }
  td:first-child { font-weight: 600; color: #1E4634; }
  .footer { margin-top: 30px; font-size: 11px; color: #999; text-align: right; }
"""

CSS_TABLE = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f5f0e4; padding: 30px; }
  .wrap { max-width: 1100px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 36px; box-shadow: 0 2px 12px rgba(30,70,52,0.1); }
  .title { font-size: 24px; font-weight: 700; color: #1E4634; margin-bottom: 6px; }
  .subtitle { font-size: 13px; color: #6E5B36; margin-bottom: 24px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { border: 1px solid #d9d2c2; padding: 10px 12px; font-size: 14px; vertical-align: top; }
  th { background: #1E4634; color: #F5F0E4; font-weight: 600; text-align: center; }
  th.dim-h { text-align: left; }
  td.dim { font-weight: 600; color: #1E4634; width: 22%; }
  td.dim .brief { display: block; font-size: 11px; color: #6E5B36; font-weight: 400; margin-top: 2px; }
  td.score { text-align: center; width: 26%; }
  tr.total-row td { background: #EEF3EE; font-weight: 600; }
  tr.eval-row td { background: #FBF8F1; }
  .group-row td { background: #6E5B36; color: #F5F0E4; font-weight: 700; font-size: 13px; letter-spacing: 0.05em; }
  .person-info { font-size: 12px; color: #999; margin-top: 2px; }
"""

CSS_LONG = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --label: #1d1d1f; --label2: #86868b; --sep: rgba(0,0,0,0.08);
    --bg: #f5f5f7; --card: #fff; --brand: #0a7d4f;
  }
  body { font-family: system-ui, -apple-system, "PingFang SC", sans-serif; background: var(--bg); color: var(--label); padding: 32px; }
  .wrap { max-width: 960px; margin: 0 auto; }
  .cover { background: var(--card); border-radius: 16px; padding: 48px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
  .cover .brand { font-size: 11px; color: var(--label2); letter-spacing: 0.08em; margin-bottom: 8px; }
  .cover h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 4px; }
  .cover .subtitle { font-size: 13px; color: var(--label2); margin-bottom: 32px; }
  .cover .org { background: #eef3ef; border-left: 3px solid var(--brand); padding: 12px 16px; border-radius: 0 8px 8px 0; margin-bottom: 28px; }
  .cover .org .label { font-size: 11px; color: var(--label2); margin-bottom: 2px; }
  .cover .org .name { font-size: 15px; font-weight: 600; color: var(--brand); }
  .base-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .base-table th, .base-table td { border: 1px solid var(--sep); padding: 10px 12px; text-align: left; }
  .base-table th { background: var(--label); color: #fff; font-weight: 600; font-size: 12px; }
  .base-table td:first-child { font-weight: 600; color: var(--brand); }
  .person { background: var(--card); border-radius: 16px; padding: 28px 32px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
  .person-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; padding-bottom: 16px; border-bottom: 1px solid var(--sep); }
  .person-name { font-size: 20px; font-weight: 700; letter-spacing: -0.01em; margin-bottom: 2px; }
  .person-info { font-size: 12px; color: var(--label2); }
  .person-scores { display: flex; gap: 24px; }
  .person-scores div { text-align: right; }
  .person-scores b { display: block; font-size: 18px; font-weight: 700; }
  .person-scores span { font-size: 11px; color: var(--label2); }
  .conclusion { background: #eef3ef; border-left: 3px solid var(--brand); border-radius: 0 8px 8px 0; padding: 10px 14px; margin-top: 16px; font-size: 12.5px; line-height: 1.6; }
  .conclusion b { color: var(--brand); }
  .overall { font-size: 13px; line-height: 1.6; color: var(--label); background: #f8f8fa; border-radius: 8px; padding: 10px 14px; margin-bottom: 20px; }
  .person-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
  .dim-group h3 { font-size: 13px; font-weight: 600; color: var(--label2); margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid var(--sep); }
  .dim-group ul { list-style: none; }
  .dim-group li { font-size: 12.5px; line-height: 1.5; padding: 4px 0; border-bottom: 1px solid var(--sep); display: flex; gap: 8px; align-items: baseline; }
  .dim-name { font-weight: 600; min-width: 64px; }
  .dim-score { font-weight: 700; min-width: 36px; }
  .dim-comment { color: var(--label2); font-size: 12px; }
"""

# 对比总表：档位配色（暗绿=突出 / 棕=常规 / 砖红=偏弱）
TABLE_BAND_COLOR = {"突出": "#1E4634", "常规": "#6E5B36", "偏弱": "#8C2F1E"}
# 苹果风长图：只区分「突出」（绿）与「其余」（灰）
LONG_GOOD = "#0a7d4f"
LONG_OTHER = "#86868b"

CN_NUM = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八",
          9: "九", 10: "十"}

# ── 截图设置：与已提交 PNG 的尺寸一一对上（反推自 reports/ 下三张 PNG）──────────
#   汇总封面 1080×900   对比总表 1180×3200   苹果风长图 2160×4440（= 1080×2220 @2x）
# ⚠ PNG 字节取决于本机 Chrome 版本：换一台机器/换一次 Chrome 升级，字节可能变但图一样。
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PNG_SETTINGS = {
    "核心人才三联测试_汇总封面": ("1080,900", 1),
    "三人核心人才三联测试_对比总表": ("1180,3200", 1),
    "三人核心人才三联测试_苹果风长图": ("1080,2220", 2),
}


def shoot_png(html_path, png_path, settings):
    """用本机 Chrome 把 HTML 截成 PNG（窗口尺寸 + 缩放与已提交产物一致）。"""
    import subprocess
    size, scale = settings or ("1200,2000", 1)
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=%d" % scale,
           "--window-size=%s" % size, "--screenshot=" + png_path,
           "file://" + os.path.abspath(html_path)]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    except Exception:
        return False
    return os.path.exists(png_path)


def cn_count(n):
    return CN_NUM.get(n, str(n))


def pct_int(score, mx):
    """百分比取整（四舍五入，.5 进位）。

    已提交产物里 15/24 显示 63%、9/24 显示 38%、21/24 显示 88% —— 都是 .5 进位，
    与 Python 内置 round() 的「银行家舍入」（62.5 → 62）不同，故用 Fraction + HALF_UP。
    """
    if not mx:
        return 0
    f = Fraction(int(score) * 100, int(mx))
    # floor(f + 1/2)：纯整数运算，无浮点误差
    return (2 * f.numerator + f.denominator) // (2 * f.denominator)


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ── 数据装配 ──────────────────────────────────────────────────────────────────
def load_spec(path):
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    for p in spec["people"]:
        p["_ctx"] = build_person_ctx(spec, p)
    return spec


def build_person_ctx(spec, p):
    """把 spec 里的一人份原始分数，装成算档位/类型/形象类比需要的上下文。

    形状与 src/build_report_docx.py 的 build_context() 对齐 —— 同一套口径，
    同一个 report_v2_profile 算档位，不另起炉灶。
    """
    dims1 = [{"key": d["key"], "name": d["name"], "score": d["score"], "max": d["max"],
              "grade": d["grade"]} for d in p["m1"]["dims"]]
    m1 = {"dims": dims1,
          "short": {"name": "", "grade": p["m1"]["short_grade"]},
          "score_text": "四维 %s 分" % "、".join(str(d["score"]) for d in dims1)}
    m2 = {"dims": [{"key": d["key"], "name": d["name"], "score": d["score"], "max": d["max"]}
                   for d in p["m2"]["dims"]],
          "total": p["m2"]["total"], "grade": p["m2"]["grade"]}
    m3 = {"dims": [{"key": d["key"], "correct": d["correct"], "total": d["total"]}
                   for d in p["m3"]["dims"]],
          "total": p["m3"]["total"], "grade": p["m3"]["grade"]}

    tb = RVP.three_band(m1, m2, m3)
    tp = RVP.type_profile(m1)
    an = RVP.animal_profile(m1, m2, m3)

    brief = {d["key"]: d["brief"] for d in spec["dimensions"]["m1"]}
    brief.update({d["key"]: d["brief"] for d in spec["dimensions"]["m2"]})
    brief.update({d["key"]: d["brief"] for d in spec["dimensions"]["m3"]})
    names = {}
    for group in ("m1", "m2", "m3"):
        for d in spec["dimensions"][group]:
            names[d["key"]] = d["name"]

    # 每个维度的：得分 / 满分 / 百分比 / 档位（百分比取整、档位按未取整值判）
    def dim_row(d, score, mx):
        return {"key": d["key"], "name": names.get(d["key"], d.get("name", "")),
                "brief": brief.get(d["key"], ""),
                "score": score, "max": mx,
                "pct": pct_int(score, mx),
                "band": RVP.dim_band3(score, mx)}

    rows = {
        "m1": [dim_row(d, d["score"], d["max"]) for d in p["m1"]["dims"]],
        "m2": [dim_row(d, d["score"], d["max"]) for d in p["m2"]["dims"]],
        "m3": [dim_row(d, d["correct"], d["total"]) for d in p["m3"]["dims"]],
    }
    parts = {x["name"]: x for x in tb["parts"]}
    return {
        "m1": m1, "m2": m2, "m3": m3,
        "rows": rows,
        "item_pct": {"性格特质": parts["性格特质"]["pct"],
                     "情绪特质": parts["情绪特质"]["pct"],
                     "逻辑评价": parts["逻辑评价"]["pct"]},
        "item_band": {"性格特质": parts["性格特质"]["band"],
                      "情绪特质": parts["情绪特质"]["band"],
                      "逻辑评价": parts["逻辑评价"]["band"]},
        "type_code": tp["code"], "type_name": tp["type_name"],
        "animal": an["name"],
        "profile": p["profile"], "prose": p["prose"], "name": p["name"],
    }


# ── 渲染：汇总封面 ────────────────────────────────────────────────────────────
def render_cover(spec):
    meta = spec["meta"]
    n = len(spec["people"])
    o = []
    o.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">')
    o.append("<title>核心人才三联测试 · 汇总封面</title>")
    o.append("<style>%s</style></head><body>" % CSS_COVER)
    o.append('<div class="wrap">')
    o.append('  <div class="brand">%s</div>' % meta["brand"])
    o.append("  <h1>核心人才三联测试 · 汇总封面</h1>")
    o.append('  <div class="subtitle">%s · %s名在职员工 · %s施测</div>'
             % (meta["date"], cn_count(n), meta["org_short_inline"]))
    o.append("")
    o.append('  <div class="org-block">')
    o.append('    <div class="org-label">施测部门</div>')
    o.append('    <div class="org-name">%s</div>' % meta["org_full"])
    o.append("  </div>")
    o.append("")
    o.append('  <div class="section-title">%s名受测人基础信息</div>' % cn_count(n))
    o.append("  <table>")
    o.append("    <thead><tr><th>姓名</th><th>性别</th><th>年龄</th><th>学历</th>"
             "<th>毕业院校 · 专业</th><th>职级</th><th>职位 · 部门</th></tr></thead>")
    o.append("    <tbody>")
    rows = []
    for p in spec["people"]:
        pf = p["profile"]
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s · %s</td>"
                    "<td>%s</td><td>%s · %s</td></tr>"
                    % (p["name"], pf["sex"], pf["age"], pf["edu"], pf["school"], pf["major"],
                       pf["hr_level"], pf["position"], pf["dept"]))
    o.append("\n".join(rows))
    o.append("    </tbody>")
    o.append("  </table>")
    o.append("")
    o.append('  <div class="footer">%s · %s</div>' % (meta["cover_footer"], meta["footer"]))
    o.append("</div>")
    o.append("</body></html>")
    return "\n".join(o)


# ── 渲染：对比总表 ────────────────────────────────────────────────────────────
def render_table(spec):
    meta = spec["meta"]
    people = spec["people"]
    o = []
    o.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">')
    o.append("<title>三人核心人才三联测试 · 对比总表</title>")
    o.append("<style>%s</style></head><body>" % CSS_TABLE)
    o.append('<div class="wrap">')
    o.append('  <div class="title">三人核心人才三联测试 · 对比总表</div>')
    o.append('  <div class="subtitle">%s · 按满分占比分三档（≥85%% 突出 / 70–85%% 常规 / '
             '&lt;70%% 偏弱）· 类型归类与形象类比见末行</div>' % meta["date"])
    o.append("  <table>")
    o.append('    <thead><tr><th class="dim-h">打分项目</th>%s</tr></thead>'
             % "".join("<th>%s</th>" % p["name"] for p in people))
    o.append("    <tbody>")

    def score_cell(ctx, row):
        color = TABLE_BAND_COLOR[row["band"]]
        return ('<td class="score">%d/%d <span style="color:%s">%d%% · %s</span></td>'
                % (row["score"], row["max"], color, row["pct"], row["band"]))

    for gi, g in enumerate(spec["groups"]):
        key = g["key"]
        o.append('      <tr class="group-row"><td colspan="4">%s、%s（%s）</td></tr>'
                 % (g["ordinal"], g["label"], g["dims"]))
        rows = people[0]["_ctx"]["rows"][key]
        for ri, row in enumerate(rows):
            dim = ("<td class=\"dim\">%s<span class=\"brief\">%s</span></td>"
                   % (row["name"], row["brief"]))
            cells = "".join(score_cell(p["_ctx"], p["_ctx"]["rows"][key][ri]) for p in people)
            indent = "      " if ri == 0 else ""
            o.append("%s<tr>%s%s</tr>" % (indent, dim, cells))
        # 小计行：三项各自的「占满分比例 · 档位」
        cells = ""
        for p in people:
            ctx = p["_ctx"]
            pct = ctx["item_pct"][g["part_name"]]
            band = ctx["item_band"][g["part_name"]]
            cells += ('<td class="total">%s<br><span style="color:%s">%.1f%% · %s</span></td>'
                      % (g["label"], TABLE_BAND_COLOR[band], pct, band))
        o.append('      <tr class="total-row"><td class="dim">%s</td>%s</tr>'
                 % (g["total_label"], cells))
        if gi == len(spec["groups"]) - 1:
            o.append("      ")

    # 末三行：类型归类 / 形象类比 / 整体评价
    o.append('<tr class="eval-row"><td class="dim">类型归类</td>%s</tr>'
             % "".join("<td>%s %s</td>" % (p["_ctx"]["type_code"], p["_ctx"]["type_name"])
                       for p in people))
    o.append('<tr class="eval-row"><td class="dim">形象类比</td>%s</tr>'
             % "".join("<td>%s</td>" % p["_ctx"]["animal"] for p in people))
    o.append('<tr class="eval-row"><td class="dim">整体评价</td>')
    for p in people:
        o.append("  <td>%s</td>" % p["_ctx"]["prose"]["eval_summary"])
    o.append("</tr>")
    o.append("    </tbody>")
    o.append("  </table>")
    o.append("</div>")
    o.append("</body></html>")
    return "\n".join(o)


# ── 渲染：苹果风长图 ──────────────────────────────────────────────────────────
def render_long(spec):
    meta = spec["meta"]
    people = spec["people"]
    n = len(people)
    o = []
    o.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">')
    o.append("<title>核心人才三联测试 · 三人综合报告</title>")
    o.append("<style>%s</style></head><body>" % CSS_LONG)
    o.append('<div class="wrap">')
    o.append('  <section class="cover">')
    o.append('    <div class="brand">%s</div>' % meta["brand"])
    o.append("    <h1>三人核心人才三联测试</h1>")
    o.append('    <div class="subtitle">%s · %s名在职员工 · %s施测</div>'
             % (meta["date"], cn_count(n), meta["org_short_inline"]))
    o.append('    <div class="org">')
    o.append('      <div class="label">施测部门</div>')
    o.append('      <div class="name">%s</div>' % meta["org_short"])
    o.append("    </div>")
    o.append('    <table class="base-table">')
    o.append("      <thead><tr><th>姓名</th><th>性别</th><th>年龄</th><th>学历</th>"
             "<th>毕业院校 · 专业</th><th>职级·薪级</th><th>机构 · 部门 · 职位</th></tr></thead>")
    o.append("      <tbody>")
    for p in people:
        pf = p["profile"]
        o.append("        <tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s · %s</td>"
                 "<td>%s</td><td>%s · %s · %s</td></tr>"
                 % (p["name"], pf["sex"], pf["age"], pf.get("edu_tier", pf["edu"]),
                    pf["school"], pf["major"],
                    pf["level_code"], pf["org"], pf["dept"], pf["position"]))
    o.append("      </tbody>")
    o.append("    </table>")
    o.append("  </section>")
    o.append("")

    for pi, p in enumerate(people):
        ctx = p["_ctx"]
        o.append('  <section class="person">')
        o.append('    <header class="person-head">')
        o.append("      <div>")
        o.append('        <div class="person-name">%s</div>' % p["name"])
        o.append('        <div class="person-info">%s %s · %s</div>'
                 % (ctx["type_code"], ctx["type_name"], ctx["animal"]))
        o.append("      </div>")
        o.append('      <div class="person-scores">')
        for label in ("人格特质", "情景处理", "逻辑分析能力"):
            part = {"人格特质": "性格特质", "情景处理": "情绪特质", "逻辑分析能力": "逻辑评价"}
            pct = ctx["item_pct"][part[label]]
            band = ctx["item_band"][part[label]]
            color = LONG_GOOD if band == "突出" else LONG_OTHER
            o.append('        <div><b style="color:%s">%.1f%%</b><span>%s</span></div>'
                     % (color, pct, label[:2]))
        o.append("      </div>")
        o.append("    </header>")
        o.append('    <div class="overall">%s</div>' % ctx["prose"]["overall_line"])
        o.append('    <div class="person-grid">')
        for g in spec["groups"]:
            key = g["key"]
            items = []
            for row in ctx["rows"][key]:
                color = LONG_GOOD if row["band"] == "突出" else LONG_OTHER
                items.append('<li><span class="dim-name">%s</span>'
                             '<span class="dim-score" style="color:%s">%d%%</span>'
                             '<span class="dim-comment">%s</span></li>'
                             % (row["name"], color, row["pct"],
                                ctx["prose"]["dim_comments"][row["key"]]))
            o.append('      <div class="dim-group"><h3>%s</h3><ul>%s</ul></div>'
                     % (g["label"], "".join(items)))
        o.append("    </div>")
        o.append('  <div class="conclusion"><b>测评结论：</b>%s</div>'
                 % ctx["prose"]["conclusion"])
        o.append("  </section>")
        if pi < len(people) - 1:
            o.append("")

    o.append("</div>")
    o.append("</body></html>")
    return "\n".join(o)


# ── 与结果 JSON 交叉核对（spec 有没有跟单份报告的原始分说岔）──────────────────
def cross_check(spec):
    """拿 pilot/out/结果JSON_*.json（若在）核对 spec 的分数与基础信息。

    这条链的意义：spec 是「转录」的，原始分是「算出来的」——两者独立来源，
    对得上才说明转录没抄错。结果 JSON 不在仓内（pilot/out 被 gitignore），
    没有就跳过，不算失败。
    """
    problems = []
    checked = 0
    for p in spec["people"]:
        path = os.path.join(ROOT, p.get("result_json", ""))
        if not os.path.exists(path):
            continue
        checked += 1
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        if raw.get("name") != p["name"]:
            problems.append("%s：结果 JSON 姓名 %r ≠ spec %r"
                            % (p["name"], raw.get("name"), p["name"]))
        for i, d in enumerate(p["m1"]["dims"]):
            j = raw["m1"]["dims"][i]
            if (d["score"], d["max"], d["grade"]) != (j["score"], j["max"], j["grade"]):
                problems.append("%s/第一项/%s：spec %s/%s(%s) ≠ JSON %s/%s(%s)"
                                % (p["name"], d["name"], d["score"], d["max"], d["grade"],
                                   j["score"], j["max"], j["grade"]))
        for i, d in enumerate(p["m2"]["dims"]):
            j = raw["m2"]["dims"][i]
            if (d["score"], d["max"]) != (j["score"], j["max"]):
                problems.append("%s/第二项/%s：spec %s/%s ≠ JSON %s/%s"
                                % (p["name"], d["name"], d["score"], d["max"],
                                   j["score"], j["max"]))
        if abs(p["m2"]["total"] - raw["m2"]["total"]) > 1e-9:
            problems.append("%s/第二项总分：spec %s ≠ JSON %s"
                            % (p["name"], p["m2"]["total"], raw["m2"]["total"]))
        for i, d in enumerate(p["m3"]["dims"]):
            j = raw["m3"]["dims"][i]
            if (d["correct"], d["total"]) != (j["correct"], j["total"]):
                problems.append("%s/第三项/%s：spec %s/%s ≠ JSON %s/%s"
                                % (p["name"], d["key"], d["correct"], d["total"],
                                   j["correct"], j["total"]))
        if abs(p["m3"]["total"] - raw["m3"]["total"]) > 1e-9:
            problems.append("%s/第三项总分：spec %s ≠ JSON %s"
                            % (p["name"], p["m3"]["total"], raw["m3"]["total"]))
        # 基础信息：spec 的拆分字段应与 JSON 的合成字段对得上
        rp = raw.get("profile") or {}
        spec_pf = p["profile"]
        if rp.get("level") and rp["level"] != spec_pf["level_code"]:
            problems.append("%s：职级码 spec %s ≠ JSON %s"
                            % (p["name"], spec_pf["level_code"], rp["level"]))
        if rp.get("school") and rp["school"] != spec_pf["school"]:
            problems.append("%s：毕业院校 spec %s ≠ JSON %s"
                            % (p["name"], spec_pf["school"], rp["school"]))
        if rp.get("major"):
            m = rp["major"]
            major = m.split("（")[0]
            edu = m.split("（")[1].rstrip("）") if "（" in m else ""
            if major != spec_pf["major"] or edu != spec_pf["edu"]:
                problems.append("%s：专业/学历 spec %s/%s ≠ JSON %s/%s"
                                % (p["name"], spec_pf["major"], spec_pf["edu"], major, edu))
        if rp.get("position"):
            parts = [x.strip() for x in rp["position"].split("·")]
            if parts[-1] != spec_pf["position"]:
                problems.append("%s：职位 spec %s ≠ JSON %s"
                                % (p["name"], spec_pf["position"], parts[-1]))
        if rp.get("unit"):
            parts = [x.strip() for x in rp["unit"].split("·")]
            if parts[0] != spec_pf["dept"]:
                problems.append("%s：部门 spec %s ≠ JSON %s"
                                % (p["name"], spec_pf["dept"], parts[0]))
    return checked, problems


# ── 入口 ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="重建三份三人对比衍生产物（HTML）")
    ap.add_argument("--spec", default=DEFAULT_SPEC, help="输入 spec（默认 src/comparison_spec.json）")
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR, help="输出目录（默认 reports/）")
    ap.add_argument("--overwrite", action="store_true", help="允许覆盖已存在且内容不同的目标文件")
    ap.add_argument("--cross-check", action="store_true",
                    help="额外与 pilot/out/结果JSON_*.json 核对 spec 的分数与基础信息")
    ap.add_argument("--print", dest="do_print", action="store_true", help="把生成的 HTML 打到标准输出")
    ap.add_argument("--png", action="store_true",
                    help="顺便用本机 Chrome 截三张 PNG（与已提交 PNG 同尺寸设置）")
    args = ap.parse_args()

    spec = load_spec(args.spec)
    stamp = (spec["meta"]["date"] or "").replace("-", "") or "00000000"
    built = {
        F_COVER % stamp: render_cover(spec),
        F_TABLE % stamp: render_table(spec),
        F_LONG % stamp: render_long(spec),
    }

    if args.cross_check:
        checked, problems = cross_check(spec)
        if not checked:
            print("交叉核对：未找到结果 JSON（pilot/out 未生成），跳过")
        elif problems:
            print("交叉核对：%d 份结果 JSON，发现 %d 处不一致" % (checked, len(problems)))
            for x in problems:
                print("  · " + x)
            return 1
        else:
            print("交叉核对：%d 份结果 JSON，spec 与原始分/基础信息全部一致" % checked)

    if args.do_print:
        for name, html in built.items():
            print("<!-- %s -->" % name)
            print(html)
        return 0

    os.makedirs(args.outdir, exist_ok=True)
    rc = 0
    for name, html in built.items():
        path = os.path.join(args.outdir, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                old = f.read()
            if old == html:
                print("一致（未改动）：%s" % path)
                continue
            if not args.overwrite:
                print("拒绝覆盖（内容不同，需 --overwrite）：%s" % path)
                rc = 1
                continue
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
        print("已写出：%s（%d B）" % (path, os.path.getsize(path)))
        if args.png:
            base = name.rsplit("_", 1)[0]      # 去掉 _20261026 尾巴
            png = os.path.join(args.outdir, base + "_" + stamp + ".png")
            ok = shoot_png(path, png, PNG_SETTINGS.get(base))
            print("  截图：%s%s" % (png, "" if ok else "（失败：Chrome 不可用？）"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
