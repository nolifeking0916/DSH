"""施测人报告内容块定义（renderer-agnostic）。

票 #78 / 口径 22：生成器（Word/PDF/HTML）、/hr/ 汇总台、离线单文件共用同一套块定义。
Python 侧的同构实现是本文件；JS 侧是 modules/report_blocks.js，
由 src/verify_block_parity.py 对同一份结果 JSON 逐块比对（块序/块名/关键字段）。

本模块只描述「有哪些块、每块取结果 JSON 的哪些字段、文案怎么拼」；
渲染（HTML / DOCX）在 report_sections.py，可信度与话术在 report_narrative.py。
"""
from __future__ import annotations

import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import report_v2_profile as V2  # noqa: E402

# 模块对外类目名（口径 23：对外一律用这三个）
NAME_M1 = "人格特质"
NAME_M2 = "情景处理"
NAME_M3 = "逻辑分析能力"
# ORDER 只用于内部强弱排序（结果 JSON 的五档是服务端口径，不在正文展示）
ORDER = ["待提升", "合格", "良好", "优秀", "顶尖"]
BAND3 = ("突出", "常规", "偏弱")
ORG = "行政管理中心 · 行政人事部 · 干部管理组"

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

    import report_v2_profile as V2
    TP = V2.type_profile(m1)
    AN = V2.animal_profile(m1, m2, m3)
    TB = V2.three_band(m1, m2, m3)
    TB_SUMMARY = " · ".join("%s %s" % (x["name"], x["band"]) for x in TB["parts"])

    blocks = []

    # ---------------- 封面页（基础信息组 + 测评信息组）
    prof = data.get("profile") or {}
    def _pf(label, key):
        v = prof.get(key)
        return (label, v if v not in (None, "") else "—")
    blocks.append({"t": "cover", "brand": "云上文旅集团 · 核心人才系列测试",
                   "title": "%s的核心人才三联测试" % (data.get("name") or "候选人"),
                   "sub": "性格特质 · 情绪特质 · 逻辑评价　|　施测人报告",
                   "fields": [("姓名", data.get("name") or "—"),
                              ("年龄", prof.get("age") or "—"),
                              ("性别", prof.get("sex") or "—"),
                              ("毕业信息", "%s · %s" % (prof.get("school") or "—", prof.get("major") or "—")),
                              ("职级", prof.get("level") or "—"),
                              ("职位及岗位", "%s · %s" % (prof.get("position") or "—", prof.get("unit") or "—")),
                              ("测评编号", data.get("code") or "—"),
                              ("身份标识", ("末 4 位 " + data["idLast4"]) if data.get("idLast4") else "—"),
                              ("报告日期", (data.get("date") or "")[:10] or "—"),
                              ("报告性质", "内部判读材料：只产出追问清单，不作录用评分项"),
                              ("施测与归档", ORG)],
                   "grade": TB_SUMMARY,
                   "score": None,
                   "band_note": TB["note"],
                   "org": ORG,
                   "notice": "本报告由测评结果生成，只用于招聘环节的面谈追问；"
                             "不作录用评分项，不设淘汰线，不构成心理或医学诊断。"
                             "候选人如对结果有疑问，可在 5 个工作日内向集团人力资源部提出复核。"})

    # ---------------- 1　整体画像（总）
    blocks.append({"t": "h1", "num": "1", "text": "整体画像"})
    blocks.append({"t": "p", "text":
                   "这位候选人的整体画像是：%s" % V2.overall_sentence(m1, m2, m3, TP, AN, TB)})
    # 1.1 形象类比
    blocks.append({"t": "h2", "text": "1.1　形象类比"})
    blocks.append({"t": "callout", "text":
                   "如果要给这三种能力找一个形象参照，最接近的是「%s」：%s。本次三项的情况是%s。"
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
        rows.append([d["name"], "%d / %d" % (d["score"], d["max"]),
                     V2.dim_band3(d["score"], d["max"]),
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
                          V2.dim_band3(ax["score"], ax["max"]), ax["desc"])})
    blocks.append({"t": "note", "text":
                   "归类口径：每个行为轴按「更有效的一端」在 24 题中的命中数归边，严格过半（13 题及以上）算偏这一侧，否则算偏另一侧，四轴拼成四字母。这是基于本测评四维行为倾向的类型化归类，与通行的心理类型量表不同：轴的含义是工作方式上的行为倾向，不是心理类型，结果不可对外当作心理类型判定使用。"})
    blocks.append({"t": "h2", "text": "2.1.1　对应详情"})
    blocks.append({"t": "table", "header": ["维度", "得分", "等级", "两极倾向（极a : 极b）", "工作方式上的表现"],
                   "rows": rows, "align": ["l", "r", "c", "l", "l"]})
    blocks.append({"t": "note", "text":
                   "「两极倾向」由 96 道两极题的逐题选择统计得出（极a : 极b，两极相当时直接标出比值），"
                   "描述的是工作方式上的倾向，不是性格类型，也不是诊断结论。"
                   "极的归口用逐题映射表 data/m1_pole_map.json（题库里 a/b 两列正反混排，"
                   "不能直接按 a/b 列的占比算）。"})
    _weak1 = min(m1["dims"], key=lambda d: d["score"] / float(d["max"] or 1))
    blocks.append({"t": "p", "text":
                   "口径：每一题是一道两极对比，两端都是行为频率陈述；每题锚定「更有效的一端」计 1 分，"
                   "每维 24 题、0–24 分，各维独立、没有总档。本部分采用绝对锚点切档，"
                   "内部样本到量后再校准参照分布。最弱的一维是 %s（%s）。"
                   % (_weak1["name"], V2.dim_band3(_weak1["score"], _weak1["max"]))})
    blocks.append({"t": "cred", "level": (cred.get("m1") or {}).get("level", "—"),
                   "text": "；".join((cred.get("m1") or {}).get("flags") or []) or "无异常信号"})

    # 2.2 情景处理（票 #81：删掉未进词汇表的「情绪特质」括注，口径 23 对外只留类目名）
    blocks.append({"t": "h2", "text": "2.2　%s分析" % NAME_M2})
    blocks.append({"t": "p", "text":
                   "这一部分看候选人在具体管理情境中的反应方式：压力下稳不稳、冲突怎么处理、"
                   "关系经营与同理沟通如何，共八个情境维度。"})
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
    _m2_part = [x for x in TB["parts"] if x["name"] == "情绪特质"][0]
    blocks.append({"t": "p", "text":
                   "总结：%s（占满分 %.1f%%，%s）。"
                   % (_m2_part["text"], _m2_part["pct"], _m2_part["band"])})
    blocks.append({"t": "h2", "text": "2.2.1　对应详情"})
    rows = []
    for d in m2["dims"]:
        nar = S.get(d["key"]) or {}
        rows.append([d["name"], d["outer_name"], "%d%%" % d["weight"], "%d / %d" % (d["score"], d["max"]),
                     V2.dim_band3(d["score"], d["max"]), nar.get("text") or d.get("read") or ""])
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

    # 2.3 逻辑分析能力总结（票 #81：删掉未进词汇表的「逻辑评价」括注）
    blocks.append({"t": "h2", "text": "2.3　%s总结" % NAME_M3})
    blocks.append({"t": "p", "text":
                   "这一部分看候选人面对陌生问题时的推理与判断：从给定条件推结论、从现象找规律、"
                   "读懂数字口径，到风险与决策偏差识别，共八个推理维度；"
                   "它不是标准化智力测验，也不与另两部分互相替代。"})
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
                     "P%s" % d["pct"], V2.band3(d["rate"]), txt])
    blocks.append({"t": "table", "header": ["维度", "正确 / 总题", "正确率", "百分位", "等级", "判读"],
                   "rows": rows, "align": ["l", "r", "r", "r", "c", "l"]})
    blocks.append({"t": "img", "path": radar_png,
                   # radar_dims：浏览器侧无 PNG 路径时据此内联 SVG（JS 同构渲染用）
                   "radar_dims": [{"key": d["key"], "short": d.get("short") or d["name"],
                                    "name": d["name"], "pct": d["pct"]} for d in m3["dims"]],
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
    # 3.0.1 三项总览：每行 = 一句话核心特征 + 保留分数
    blocks.append({"t": "h2", "text": "3.0.1　三项总览"})
    blocks.append({"t": "table",
                   "header": ["测试", "核心特征", "得分（占满分 · 档位）"],
                   "rows": [[x["name"], x["text"], "%s · %.1f%% · %s" % (x["score_text"], x["pct"], x["band"])]
                            for x in TB["parts"]],
                   "align": ["l", "l", "r"]})
    blocks.append({"t": "h2", "text": "3.0.2　提升方向"})
    if TB["gap_to_top"] <= 0:
        blocks.append({"t": "callout", "text":
                       "三项都在突出水平，没有明显短板；接下来的成长更多来自经验与场景复杂度，而不是补哪一项。"})
    else:
        blocks.append({"t": "callout", "text":
                       "最值得补的是%s（当前 %.1f%%，%s）；补到 85%% 还差 %.1f 个百分点。"
                       % (TB["weakest"]["name"], TB["weakest"]["pct"], TB["weakest"]["band"],
                          TB["gap_to_top"])})
    blocks.append({"t": "p", "text":
                   "提升方向只看最弱的那一项，不做跨项合成：这一项补上来，最明显的短板就消失了，其余两项维持现状即可。"})
    blocks.append({"t": "h2", "text": "3.0.3　适合的方向"})
    blocks.append({"t": "p", "text": ov("fit", "综合三类测试的表现，下面给出方向性建议；具体岗位还需结合专业技能与工作样本。")})
    blocks.append({"t": "p", "text": ov("potential", "潜力判断以现有分数与短板分布为依据，成长空间主要取决于短板维度。")})
    blocks.append({"t": "h2", "text": "3.0.4　面谈追问清单"})
    blocks.append({"t": "note", "text": "测评只产出追问清单，不作录用评分项。下列问题按短板与复核项生成，供面谈现场取证："})
    blocks.append({"t": "ol", "items": compose.get("questions") or []})
    blocks.append({"t": "h2", "text": "3.0.5　使用边界"})
    blocks.append({"t": "kv", "rows": [
        ["结果性质", "只产出追问清单，不作录用评分项；同一岗位对所有候选人使用同一套题、同一权重、同一阈值。"],
        ["与面试冲突时", "以面试与工作样本为主，并记录冲突原因。"],
        ["不是淘汰线", "本产品不设淘汰线；三档档位与单项等级同样不产生淘汰动作。"],
        ["不做什么", "不测量性格，不测量智力，不属于临床心理评估，不对心理健康状况作判断。"],
        ["谁能看到", "集团人力资源部 2–3 名工作人员（含用人部门负责人）在施测工作台查看并讨论，用于招聘环节的评估；自测期工作台入口暂未设访问鉴权，该暴露面已按票 #36 记录在案。"],
        ["留存与复核", "交卷记录（含逐题作答与三项分数）留存集团人力资源部系统，测试数据保留不超过 1 年，到期删除或匿名化；查询、更正、删除由集团人力资源部受理，候选人可在提交后 5 个工作日内提出复核。"],
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
