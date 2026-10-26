#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""施测人报告的**新版装配**：总 → 分 → 总 + 封面页。

结构（维护者 2026-10-25 定）：
  封面页（独立一页）
  一、总体画像（总）：性格画像 → 本次作答的可信度 → 三类能力的总体表现
  二、分项详评（分）：人格特质 / 情景处理 / 逻辑分析能力，每节带可信度
  三、整体评价（总）：适合的方向、潜力、擅长与不擅长、追问清单、使用边界
  附录：结论口径与使用边界

命名：不再出现「第一项 / 第二项 / 第三项」，一律用
      人格特质 / 情景处理 / 逻辑分析能力。

内容块（blocks）只写一遍，Word 与 HTML 两套渲染器共用 ⇒ 仍是「同源同数」。
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import build_report_docx as B          # 复用 Word 侧的排版helper
from report_narrative import build_profile, fetch_narrative, credibility

NAME_M1 = "人格特质"
NAME_M2 = "情景处理"
NAME_M3 = "逻辑分析能力"
ORDER = ["待提升", "合格", "良好", "优秀", "顶尖"]

ORG = "浙江云上文旅集团 · 行政管理中心 · 行政人事部 · 干部管理组"


# ---------------------------------------------------------------- 小工具
def band_badge(grade):
    return B.LV_INK.get(grade, B.INK)


def _safe(s):
    return "" if s is None else str(s)


# ---------------------------------------------------------------- 内容块
def build_blocks(data, m1, m2, m3, compose, m1meta, narrative, cred, radar_png, profile=None):
    """把报告内容组装成块列表（与渲染方式无关）。"""
    P = narrative.get("personality") or {}
    S = narrative.get("situation") or {}
    R = narrative.get("reasoning") or {}
    O = {}
    for item in (narrative.get("overall") or []):
        O[item.get("kind")] = item

    def ov(kind, fallback=""):
        it = O.get(kind)
        if it and it.get("text"):
            return it["text"]
        return fallback

    blocks = []

    # ---------------- 封面页
    blocks.append({"t": "cover", "brand": "云上文旅集团 · 核心人才系列测试",
                   "title": "%s的核心人才三联测试" % (data.get("name") or "候选人"),
                   "sub": "性格特质 · 情绪特质 · 逻辑评价　|　施测人报告",
                   "fields": [("候选人", data.get("name") or "—"),
                              ("测评编号", data.get("code") or "—"),
                              ("身份标识", ("末 4 位 " + data["idLast4"]) if data.get("idLast4") else "—"),
                              ("报告日期", (data.get("date") or "")[:10] or "—"),
                              ("报告性质", "内部判读材料：只产出追问清单，不作录用评分项"),
                              ("施测与归档", ORG)],
                   "grade": compose.get("grade"),
                   "score": compose.get("score"),
                   "org": ORG,
                   "notice": "本报告由测评结果生成，只用于招聘环节的面谈追问；"
                             "不作录用评分项，不设淘汰线，不构成心理或医学诊断。"
                             "候选人如对结果有疑问，可在 5 个工作日内向集团人力资源部提出复核。"})

    # ---------------- 1　整体画像（总）
    import report_v2_profile as V2
    TP = V2.type_profile(m1)
    AN = V2.animal_profile(m1, m2, m3)
    TA = V2.talent_score(m1, m2, m3)
    blocks.append({"t": "h1", "num": "1", "text": "整体画像"})
    blocks.append({"t": "p", "text":
                   "这位候选人的整体画像是：%s" % V2.overall_sentence(m1, m2, m3, TP, AN, TA)})
    # 1.1 形象类比
    blocks.append({"t": "h2", "text": "1.1　形象类比"})
    blocks.append({"t": "callout", "text":
                   "如果要给这三种能力找一个形象参照，最接近的是「%s」：%s。本次三项的表现属于%s。"
                   % (AN["name"], AN["why"], AN["strength"])})
    blocks.append({"t": "note", "text":
                   "类比只用来帮施测人快速形成印象（取自行为倾向的三个关键轴：主动推动 / 等待配合、事实先行 / 趋势先导、定时收口 / 随机应对），不构成任何结论，也不是对候选人的评价性标签。"})
    # 1.2 本次作答的可信度
    blocks.append({"t": "h2", "text": "1.2　本次作答的可信度"})
    # 可信度低时，先说清楚：下面的画像不能当结论用
    cred1 = cred.get("m1") or {}
    if cred1.get("level") == "低":
        blocks.append({"t": "callout", "text":
                       "本次人格特质的作答可信度为「低」（%s）——"
                       "下面这段画像只作参考，不能当成结论；建议先让候选人重测一遍再判读。"
                       % "；".join(cred1.get("flags") or [])})
    rows = []
    prof1 = (profile or {}).get("personality") or {}
    for d in m1["dims"]:
        nar = P.get(d["key"]) or {}
        pf = prof1.get(d["key"]) or {}
        a_cnt, b_cnt = pf.get("a_cnt"), pf.get("b_cnt")
        if a_cnt is None or b_cnt is None:
            side = nar.get("pole_label") or "—"
        elif abs(a_cnt - b_cnt) <= 3:
            side = "两极相当（%d : %d）" % (a_cnt, b_cnt)
        else:
            side = "%s（%d : %d）" % (nar.get("pole_label") or "—", a_cnt, b_cnt)
        rows.append([d["name"], "%d / %d" % (d["score"], d["max"]), d["grade"],
                     side, nar.get("text") or d.get("brief") or ""])

    # 可信度
    crows = []
    for key, label in (("m1", NAME_M1), ("m2", NAME_M2), ("m3", NAME_M3)):
        c = cred.get(key) or {}
        flags = "；".join(c.get("flags") or []) or "无异常信号"
        crows.append([label, c.get("level", "—"), flags])
    blocks.append({"t": "table", "header": ["部分", "可信度", "依据"], "rows": crows,
                   "align": ["l", "c", "l"]})
    blocks.append({"t": "note", "text":
                   "可信度回答的是「这份结果能不能信」，不是「这个人行不行」。"
                   "判据：同侧作答（连续选同一端的长度与偏向比例）、未作答比例、"
                   "成对题的一致性、以及整卷节奏%s。可信度偏低时，"
                   "下面的分数只作参考，面试取证优先。" % (("（%s）" % cred["overall"]["speed"]) if cred.get("overall", {}).get("speed") else "")})

    # 三类能力总表

    # ---------------- 二、分项详评（分）
    blocks.append({"t": "h1", "num": "2", "text": "分项"})

    # 2.1 性格特质 · 类型归类
    blocks.append({"t": "h2", "text": "2.1　%s · 类型归类" % NAME_M1})
    blocks.append({"t": "callout", "text":
                   "%s（%s）· %s" % (TP["type_name"] or "未定型", TP["code"], TP["type_desc"])})
    blocks.append({"t": "p", "text":
                   "按四个行为轴归类：%s。" % TP["summary"]})
    for ax in TP["axes"]:
        blocks.append({"t": "p", "text":
                       "%s（%s 轴）：%s（%d / %d，%s）——%s。"
                       % (ax["name"], ax["axis"], ax["side_label"], ax["score"], ax["max"],
                          ax["grade"], ax["desc"])})
    blocks.append({"t": "note", "text":
                   "归类口径：每个行为轴按「更有效的一端」在 24 题中的命中数归边，严格过半（13 题及以上）算偏这一侧，否则算偏另一侧，四轴拼成四字母。这是基于本测评四维行为倾向的类型化归类，与通行的 MBTI 测评题不同、轴的含义也不同（此处是工作方式上的行为倾向，不是心理类型），不可当作 MBTI 结果对外使用。"})
    blocks.append({"t": "h2", "text": "2.1.1　对应详情"})
    blocks.append({"t": "table", "header": ["维度", "得分", "等级", "两极倾向（极a : 极b）", "工作方式上的表现"],
                   "rows": rows, "align": ["l", "r", "c", "l", "l"]})
    blocks.append({"t": "note", "text":
                   "「两极倾向」由 96 道两极题的逐题选择统计得出（极a : 极b，两极相当时直接标出比值），"
                   "描述的是工作方式上的倾向，不是性格类型，也不是诊断结论。"
                   "极的归口用逐题映射表 data/m1_pole_map.json（题库里 a/b 两列正反混排，"
                   "不能直接按 a/b 列的占比算）。"})
    blocks.append({"t": "p", "text":
                   "口径：每一题是一道两极对比，两端都是行为频率陈述；每题锚定「更有效的一端」计 1 分，"
                   "每维 24 题、0–24 分，各维独立、没有总档。本部分采用绝对锚点切档，"
                   "内部样本到量后再校准参照分布。最弱的一维是 %s。" % m1["short_text"]})
    blocks.append({"t": "cred", "level": (cred.get("m1") or {}).get("level", "—"),
                   "text": "；".join((cred.get("m1") or {}).get("flags") or []) or "无异常信号"})

    # 2.2 情绪特质（情景处理）
    blocks.append({"t": "h2", "text": "2.2　%s（%s）分析" % (NAME_M2, "情绪特质")})
    strong = sorted([d for d in m2["dims"] if d["grade"] in ("顶尖", "优秀")],
                    key=lambda d: -ORDER.index(d["grade"]))[:3]
    weak = sorted([d for d in m2["dims"] if d["grade"] in ("合格", "待提升")],
                  key=lambda d: ORDER.index(d["grade"]))[:3]
    if not strong:
        strong = sorted(m2["dims"], key=lambda d: -ORDER.index(d["grade"]))[:2]
    if not weak:
        weak = sorted(m2["dims"], key=lambda d: ORDER.index(d["grade"]))[:2]
    TR = V2.PROFILES["m2_traits"]
    def _trait_line(dim, field):
        tt = (TR.get(dim["key"]) or {}).get(field, dim.get("read", ""))
        return "%s——%s" % (dim["name"], tt)
    blocks.append({"t": "kv", "rows": [
        ["善于什么", "；".join([_trait_line(d, "strong") for d in strong])],
        ["不善于什么", "；".join([_trait_line(d, "weak") for d in weak])]]})
    blocks.append({"t": "p", "text": "总结：%s" % V2.PROFILES["m2_summary"].get(m2["grade"], "")})
    blocks.append({"t": "h2", "text": "2.2.1　对应详情"})
    rows = []
    for d in m2["dims"]:
        nar = S.get(d["key"]) or {}
        rows.append([d["name"], d["outer_name"], "%d%%" % d["weight"], "%d / %d" % (d["score"], d["max"]),
                     d["grade"], nar.get("text") or d.get("read") or ""])
    blocks.append({"t": "table", "header": ["维度", "归属", "权重", "得分", "等级", "判读"], "rows": rows,
                   "align": ["l", "l", "r", "r", "c", "l"]})
    blocks.append({"t": "p", "text":
                   "口径：八个管理情境维度上的行为反应，每维 6 道计分题（每题满分 2 分）、"
                   "折算成 0–12 分；模块总分按权重加权到 0–5.00。"
                   "自评折算与情境折算差异 ≥ 1.0 的维度标为「需复核」。"})
    if m2.get("consistency"):
        blocks.append({"t": "table", "header": ["题对", "判定", "作答"],
                       "rows": [[c["pair"], c["status"], c["detail"]] for c in m2["consistency"]],
                       "align": ["l", "l", "l"], "caption": "一致性检查（同一致情境的两种问法是否指向同一倾向；不计入任何维度分）"})
    if m2.get("need_review"):
        blocks.append({"t": "callout", "text":
                       "需复核：%s —— 自我参照与情境作答差异较大，按「需结合真实经历再确认」处理，"
                       "不直接采信任一方。" % "、".join(m2["need_review"])})
    blocks.append({"t": "cred", "level": (cred.get("m2") or {}).get("level", "—"),
                   "text": "；".join((cred.get("m2") or {}).get("flags") or []) or "无异常信号"})

    # 2.3 逻辑能力总结
    blocks.append({"t": "h2", "text": "2.3　%s（%s）总结" % (NAME_M3, "逻辑评价")})
    strong3 = sorted([d for d in m3["dims"] if d["grade"] in ("顶尖", "优秀")],
                     key=lambda d: -ORDER.index(d["grade"]))[:3]
    weak3 = sorted([d for d in m3["dims"] if d["grade"] in ("合格", "待提升")],
                   key=lambda d: ORDER.index(d["grade"]))[:3]
    if not strong3:
        strong3 = sorted(m3["dims"], key=lambda d: -ORDER.index(d["grade"]))[:2]
    if not weak3:
        weak3 = sorted(m3["dims"], key=lambda d: ORDER.index(d["grade"]))[:2]
    def _log_line(dim, field):
        return "%s——%s" % (dim["name"], dim.get(field) or "")
    blocks.append({"t": "kv", "rows": [
        ["善于", "；".join([_log_line(d, "high") for d in strong3])],
        ["不善于", "；".join([_log_line(d, "low") for d in weak3])]]})
    blocks.append({"t": "h2", "text": "2.3.1　对应详情"})
    rows = []
    for d in m3["dims"]:
        nar = R.get(d["key"]) or {}
        txt = nar.get("text") or ""
        if not txt:
            txt = d.get("high") or ""
        rows.append([d["name"], "%d / %d" % (d["correct"], d["total"]), "%d%%" % d["rate"],
                     "P%s" % d["pct"], d["grade"], txt])
    blocks.append({"t": "table", "header": ["维度", "正确 / 总题", "正确率", "百分位", "等级", "判读"],
                   "rows": rows, "align": ["l", "r", "r", "r", "c", "l"]})
    if radar_png:
        blocks.append({"t": "img", "path": radar_png,
                       "caption": "%s 八维参考分布百分位（雷达几何刻度 = 百分位，与上表同口径；"
                                  "金色虚线 = 中位 P50，灰色虚线 = P25）" % NAME_M3})
    blocks.append({"t": "p", "text":
                   "口径：难度加权答对 %s 分，落在内置参考分布的第 %s 百分位、T 分 %s。"
                   "百分位基于按题目难度加权的理论模型换算，不是商业常模，也不等同任何标准化智力测验；"
                   "档位以百分位为准。" % (m3["total"], m3["pct"], m3["t"])})
    blocks.append({"t": "cred", "level": (cred.get("m3") or {}).get("level", "—"),
                   "text": "；".join((cred.get("m3") or {}).get("flags") or []) or "无异常信号"})

    # ---------------- 3.0　人才综合素质与潜力（总）
    blocks.append({"t": "h1", "num": "3.0", "text": "人才综合素质与潜力"})
    # 3.0.1 三类表现 + 综合素质给分
    blocks.append({"t": "h2", "text": "3.0.1　综合素质"})
    # 三类测试的表现（总表）
    blocks.append({"t": "table",
                   "header": ["测试", "分数口径", "得分", "等级", "最弱的一维"],
                   "rows": [[NAME_M1, "四维 0–24 分（各维独立，无总档）", m1["score_text"], "无总档", m1["short_text"]],
                            [NAME_M2, "八维加权 0–5.00", "%.2f / 5.00" % m2["total"], m2["grade"], m2["short_text"]],
                            [NAME_M3, "难度加权 0–40 → 参考分布百分位",
                             "%.1f 分 · P%s · T %s" % (m3["total"], m3["pct"], m3["t"]),
                             m3["grade"], m3["short_text"]]],
                   "align": ["l", "l", "r", "c", "l"]})
    # 综合素质给分
    blocks.append({"t": "callout", "text":
                   "人才综合素质：%.1f / 100（%s）" % (TA["comprehensive"], TA["grade"])})
    blocks.append({"t": "table",
                   "header": ["构成面", "归一分", "折算口径"],
                   "rows": [[x["name"], "%.1f / 100" % x["pct"], x["basis"]] for x in TA["parts"]] +
                            [["综合素质", "%.1f / 100" % TA["comprehensive"],
                              "三面归一后等权平均（%s）" % TA["grade"]]],
                   "align": ["l", "r", "l"]})
    blocks.append({"t": "p", "text":
                   "综合评估 %s（三类等级等权合成，序数分 %.2f / 5）。%s"
                   % (compose["grade"], compose["score"], TA["talent_text"])})
    blocks.append({"t": "note", "text":
                   "综合素质分的口径：性格面取四维命中率平均，情绪面取加权总分 ÷ 5.00，"
                   "逻辑面取参考分布百分位，三面归一到 0–100 后等权平均。"
                   + "它把三类能力放在同一把尺子上看，不是加总原始分，也不产生淘汰动作。"})
    blocks.append({"t": "p", "text": ov("fit", "综合三类测试的表现，下面给出方向性建议；具体岗位还需结合专业技能与工作样本。")})
    blocks.append({"t": "h2", "text": "3.0.2　潜力"})
    blocks.append({"t": "callout", "text":
                   "潜力可达：%.1f / 100（%s）；相对当前 %.1f 分，结构空间 %.1f 分。%s"
                   % (TA["potential"], TA["potential_grade"], TA["comprehensive"], TA["space"],
                      TA["potential_note"])})
    blocks.append({"t": "p", "text":
                   "潜力分的算法：把最短板的那一面（本次是%s）补到三类平均水平，其余两面不动，得到的综合分就是可达水平；与当前分的差就是结构空间。这是基于本次三项结构的推算、不是预测：空间大说明短板补上来收益明显，空间小说明已经接近这套结构的上限，接下来更多靠经验与场景复杂度。"
                   % TA["short_name"]})
    blocks.append({"t": "p", "text": ov("potential", "潜力判断以现有分数与短板分布为依据，成长空间主要取决于短板维度。")})

    blocks.append({"t": "h2", "text": "3.0.4　面谈追问清单"})
    blocks.append({"t": "note", "text": "测评只产出追问清单，不作录用评分项。下列问题按短板与复核项生成，供面谈现场取证："})
    blocks.append({"t": "ol", "items": compose.get("questions") or []})
    blocks.append({"t": "h2", "text": "3.0.5　使用边界"})
    blocks.append({"t": "kv", "rows": [
        ["结果性质", "只产出追问清单，不作录用评分项；同一岗位对所有候选人使用同一套题、同一权重、同一阈值。"],
        ["与面试冲突时", "以面试与工作样本为主，并记录冲突原因。"],
        ["不是淘汰线", "本产品不设淘汰线；综合评估与单项等级同样不产生淘汰动作。"],
        ["不做什么", "不测量性格，不测量智力，不属于临床心理评估，不对心理健康状况作判断。"],
        ["谁能看到", "集团人力资源部 2–3 名工作人员（含用人部门负责人），用于招聘环节的评估；不向其他人提供。"],
        ["留存与复核", "结果由集团人力资源部归档；候选人如对结果有疑问，可在 5 个工作日内提出复核。"],
        ["施测与归档单位", ORG],
    ]})

    # ---------------- 附录
    blocks.append({"t": "h1", "num": "附录", "text": "结论口径与使用边界"})
    blocks.append({"t": "p", "text": ov("conclusion",
                   "以上只说明这位候选人在常规工作方式、具体管理情境、陌生问题推理三个切面上的表现倾向，"
                   "不说明能力高低，不诊断性格，也不作录用评分项。")})
    blocks.append({"t": "p", "text": ov("boundary",
                   "录用决策应由简历、专业技能、面谈与工作样本等多源证据支撑；测评与面试冲突时以面试与工作样本为主。")})
    blocks.append({"t": "p", "text": ov("method",
                   "本报告的三类测试互不替代：%s看工作方式上的倾向，%s看在具体管理情境里的反应，"
                   "%s看陌生问题上的推理与判断。三者同涨同跌时需要复核题目是否重叠，而不是直接加分。"
                   % (NAME_M1, NAME_M2, NAME_M3))})
    blocks.append({"t": "kv", "rows": [
        ["报告名称", "%s的核心人才三联测试" % (data.get("name") or "候选人")],
        ["施测与归档单位", ORG],
        ["报告日期", (data.get("date") or "")[:10] or "—"],
        ["测评编号", data.get("code") or "—"],
    ]})
    return blocks

# ================================================================ 渲染：HTML
def _esc(s):
    return B.esc(s)


def render_html_blocks(blocks, radar_b64=None):
    o = []
    A = o.append
    for b in blocks:
        t = b["t"]
        if t == "cover":
            A('<section class="coverpage">')
            A('<div class="coverpage-brand">%s</div>' % _esc(b["brand"]))
            A('<h1 class="coverpage-title">%s</h1>' % _esc(b["title"]))
            A('<p class="coverpage-sub">%s</p>' % _esc(b["sub"]))
            A('<table class="kv coverpage-kv">')
            for k, v in b["fields"]:
                A('<tr><td class="k">%s</td><td>%s</td></tr>' % (_esc(k), _esc(v)))
            A("</table>")
            A('<p class="coverpage-grade"><span class="coverpage-label">综合评估</span>'
              '<span class="lv %s">%s</span>'
              '<span class="coverpage-score">三类等级等权合成，序数分 %.2f / 5</span></p>'
              % (B.lv_class(b["grade"]), _esc(b["grade"]), b["score"]))
            A('<p class="coverpage-org">%s</p>' % _esc(b["org"]))
            A('<p class="coverpage-notice">%s</p>' % _esc(b["notice"]))
            A("</section>")
        elif t == "h1":
            A('<div class="sec"><h1>%s、%s</h1>' % (_esc(b["num"]), _esc(b["text"])))
        elif t == "h2":
            A('<h2>%s</h2>' % _esc(b["text"]))
        elif t == "p":
            A('<p>%s</p>' % _esc(b["text"]))
        elif t == "note":
            A('<p class="note">%s</p>' % _esc(b["text"]))
        elif t == "callout":
            A('<div class="callout">%s</div>' % _esc(b["text"]))
        elif t == "cred":
            lv = {"高": "lv-A", "中": "lv-C", "低": "lv-D"}.get(b.get("level"), "lv-B")
            A('<p class="cred"><span class="cred-label">可信度</span>'
              '<span class="lv %s">%s</span>'
              '<span class="cred-text">%s</span></p>' % (lv, _esc(b.get("level")), _esc(b.get("text"))))
        elif t == "kv":
            A('<table class="kv">')
            for k, v in b["rows"]:
                A('<tr><td class="k">%s</td><td>%s</td></tr>' % (_esc(k), _esc(v)))
            A("</table>")
        elif t == "table":
            align = b.get("align") or []
            A('<table class="tbl"><thead><tr>')
            for i, htxt in enumerate(b["header"]):
                cls = ""
                if i < len(align) and align[i] == "r":
                    cls = ' class="r"'
                elif i < len(align) and align[i] == "c":
                    cls = ' class="c"'
                A("<th%s>%s</th>" % (cls, _esc(htxt)))
            A("</tr></thead><tbody>")
            for row in b["rows"]:
                A("<tr>")
                for i, v in enumerate(row):
                    cls = ""
                    if i < len(align) and align[i] == "r":
                        cls = ' class="r num"'
                    elif i < len(align) and align[i] == "c":
                        cls = ' class="c"'
                    txt = _esc(v)
                    if v in ORDER:
                        txt = '<span class="lv %s">%s</span>' % (B.lv_class(v), txt)
                    A("<td%s>%s</td>" % (cls, txt))
                A("</tr>")
            A("</tbody></table>")
            if b.get("caption"):
                A('<p class="cap">%s</p>' % _esc(b["caption"]))
        elif t == "ol":
            A('<ol class="qs">')
            for it in b["items"]:
                A("<li>%s</li>" % _esc(it))
            A("</ol>")
        elif t == "img":
            if radar_b64:
                A('<div class="radar"><img src="data:image/png;base64,%s" alt="八维百分位雷达图"></div>' % radar_b64)
                A('<p class="cap">%s</p>' % _esc(b.get("caption", "")))
    return "".join(o)


# ================================================================ 渲染：Word
def render_docx_blocks(doc, blocks, radar_png=None):
    for b in blocks:
        t = b["t"]
        if t == "cover":
            t_ = doc.add_table(rows=1, cols=1)
            t_.alignment = B.WD_TABLE_ALIGNMENT.LEFT
            B.no_borders(t_)
            c = t_.rows[0].cells[0]
            B.shade(c, B.GREEN)
            B.cell_margins(c, top=500, left=320, bottom=420, right=320)
            c.text = ""
            p = c.paragraphs[0]
            p.paragraph_format.space_after = B.Pt(6)
            B.run_fmt(p.add_run(b["brand"]), size=11, color=B.GOLD, cn=B.CN_HEAD)
            p2 = c.add_paragraph()
            p2.paragraph_format.space_after = B.Pt(3)
            B.run_fmt(p2.add_run(b["title"]), size=28, bold=True, color=B.CREAM, cn=B.CN_HEAD)
            p3 = c.add_paragraph()
            p3.paragraph_format.space_after = B.Pt(0)
            B.run_fmt(p3.add_run(b["sub"]), size=12, color=B.CREAM, cn=B.CN_FONT)
            B.para(doc, "", after=14)
            B.kv_table(doc, b["fields"], widths=(3.4, 11.8))
            B.para(doc, "", after=8)
            p = B.para(doc, "", after=6)
            B.run_fmt(p.add_run("综合评估　"), size=13, bold=True, color=B.GREEN, cn=B.CN_HEAD)
            B.run_fmt(p.add_run(b["grade"]), size=13, bold=True,
                      color=B.LV_INK.get(b["grade"], B.INK), cn=B.CN_HEAD)
            B.run_fmt(p.add_run("　（三类等级等权合成，序数分 %.2f / 5）" % b["score"]),
                      size=10.5, color=B.INK2, cn=B.CN_FONT)
            B.para(doc, "", after=10)
            B.rich(doc, [(b["org"], {"bold": True, "color": B.GREEN, "cn": B.CN_HEAD, "size": 11.5})],
                   after=6)
            B.para(doc, b["notice"], size=9.5, color=B.INK2, cn=B.CN_FONT, align="justify", after=6)
            B.page_break(doc)
        elif t == "h1":
            B.h1(doc, b["text"], b.get("num"))
        elif t == "h2":
            B.h2(doc, b["text"])
        elif t == "p":
            B.para(doc, b["text"], size=10.5, color=B.INK, cn=B.CN_FONT, align="justify", after=6)
        elif t == "note":
            B.para(doc, b["text"], size=9.5, color=B.INK2, cn=B.CN_FONT, align="justify", after=6)
        elif t == "callout":
            B.para(doc, b["text"], size=10.5, color=B.INK, cn=B.CN_FONT, align="justify", after=8)
        elif t == "cred":
            p = B.para(doc, "", after=8)
            B.run_fmt(p.add_run("本次作答可信度　"), size=10.5, bold=True, color=B.GREEN, cn=B.CN_HEAD)
            B.run_fmt(p.add_run(b.get("level", "—")), size=10.5, bold=True, color=B.INK, cn=B.CN_HEAD)
            B.run_fmt(p.add_run("　" + (b.get("text") or "")), size=10, color=B.INK2, cn=B.CN_FONT)
        elif t == "kv":
            B.kv_table(doc, b["rows"], widths=(3.4, 11.8))
        elif t == "table":
            align = b.get("align") or []
            aligns = ["left"] * len(b["header"])
            for i, a in enumerate(align):
                if i < len(aligns):
                    aligns[i] = "right" if a == "r" else ("center" if a == "c" else "left")
            level_col = None
            for i in range(len(b["header"])):
                vals = [str(r[i]) for r in b["rows"] if i < len(r)]
                if vals and all(v in ORDER for v in vals):
                    level_col = i
                    break
            widths = _widths(len(b["header"]))
            B.grid_table(doc, b["header"], [[str(v) for v in row] for row in b["rows"]],
                         widths, aligns=aligns, level_col=level_col)
            if b.get("caption"):
                B.para(doc, b["caption"], size=9, color=B.INK2, cn=B.CN_FONT,
                       align="center", after=8)
        elif t == "ol":
            for i, it in enumerate(b["items"], 1):
                B.rich(doc, [("%d. " % i, {"bold": True, "color": B.GOLD, "en": B.EN_FONT, "size": 11}),
                             (it, {})], after=5, indent=0.5, align="justify")
        elif t == "img":
            if radar_png and os.path.exists(radar_png):
                try:
                    doc.add_picture(radar_png, width=B.Cm(13.6))
                    doc.paragraphs[-1].alignment = B.WD_ALIGN_PARAGRAPH.CENTER
                except Exception:
                    pass
                if b.get("caption"):
                    B.para(doc, b["caption"], size=9, color=B.INK2, cn=B.CN_FONT,
                           align="center", after=8)


def _widths(n):
    total = 15.2
    if n <= 1:
        return (total,)
    base = total / float(n)
    return tuple(round(base, 2) for _ in range(n))

