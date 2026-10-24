# -*- coding: utf-8 -*-
"""生成《候选人测试二 · 情商与关系管理测试》设计与结果呈现 HTML 报告。
风格沿用集团既有汇报页（深绿 #1E4634 + 米白 #F5F0E4 + 金 #C9A55C），自包含单文件、无外链。
评分口径对齐集团既有称职度评估：0–5 分制、加权分 + 单项下限、结论「行 / 不行」。
模型与工具口径依据同日调研简报《EQ测评调研简报_2026-10-24.md》。
"""
import math, os

OUT = os.path.expanduser("~/Downloads/候选人测试二_情商测试_设计与结果呈现_20261024.html")

# ---------------- 维度数据（教练版 8 子维 → 对外 4 维） ----------------
# key, 名称, 权重, 对外维度key, 5分锚点, 3分锚点, 1分锚点, 观察信号, 追问脚本, 示例分
DIMS = [
    ("self", "自我觉察", 9, "A",
     "能主动复盘情绪触发点（说得出「我当时心里第一反应是什么」），并据此调整；自评与行为证据基本一致。",
     "知道自己情绪波动大的场景，但描述笼统（「我脾气不太好」），改进动作偶发、难持续。",
     "把外因归给环境与他人（「都是他们不理解」），追问三次仍停在「我没错」；自评与他评严重背离。",
     "STAR 叙述里「我 / 我们」的比例；是否出现情绪觉察类自述句。",
     "讲一次你被下属或客户否定建议的经历。当时你心里第一反应是什么？你怎么处理的？如果重来会怎么做？", 3.5),
    ("regu", "情绪稳定", 15, "A",
     "被当众质疑后仍能继续推进事务，事后不迁怒；高压节点仍按节奏交付。",
     "能控制当场情绪，但事后反复内耗，或在非正式场合抱怨。",
     "情绪外溢（摔话、甩脸色、事后报复性分配任务），或压力下直接放弃职责。",
     "压力面谈中的语速与停顿；是否出现「就是气不过」类归因。",
     "讲一次你在高压节点（大型活动开园、集中客诉、上级临时加码）处理失当或险些失当的经历，当时你怎么稳住的？", 4.2),
    ("empa", "同理心", 12, "B",
     "在对方说出诉求前就能调整做法；能为不同立场的人分别说出其合理诉求。",
     "能理解显性诉求，但对情绪与潜台词识别偏慢，需要对方明说才反应过来。",
     "把情绪化表达当噪音（「他在无理取闹」），忽略他人感受带来的直接成本。",
     "复述他人情绪是否准确；是否使用「他其实是担心……」句式。",
     "讲一次你察觉同事情绪异常并主动介入的经历。你是怎么判断出他不对劲的？", 3.6),
    ("comm", "倾听表达", 10, "B",
     "复述对方观点准确，能用对方的语言说清结论；对方表达完之后能自然续讲。",
     "能听完，但复述有偏差；表达偏「信息堆叠」，对方需要二次确认。",
     "抢话、以说代听；表达让对方明显不适或转入防御。",
     "复述偏差；是否出现信息堆叠、需对方二次确认。",
     "讲一次你因为没听懂对方真实诉求而返工的沟通。你后来是怎么补上这一课的？", 3.0),
    ("conf", "冲突处理", 15, "C",
     "能在公开场合处理分歧而不伤关系，冲突后合作效率不下降。",
     "私下沟通能解决，但公开或跨部门场景倾向回避与拖延，私下解决后再把情绪带进流程。",
     "回避、背后议论、迁怒第三方，或用权压服。",
     "冲突是否公开处理；是否出现「私下我们…」式回避。",
     "讲一次你和同事或上级有明确利益冲突的经历。你怎么处理的？后来关系和工作各是什么结果？", 2.4),
    ("rela", "关系经营", 15, "D",
     "与上级、平级、下属都能建立稳定信任，在需要时借得到力。",
     "关系维持尚可，合作多靠流程与上级推动，主动经营不足。",
     "关系只用于办事，人情与立场绑定；被提醒后仍不调整。",
     "是否记住并回应对方过往关注点；跨机构合作的主动联络频次。",
     "讲一次你主动修复一段恶化的工作关系。你做了什么让对方愿意重新合作？", 3.6),
    ("infl", "影响力说服", 13, "D",
     "能用事实与他人利益说服人，在存在反对意见时仍能推动落地。",
     "靠职级与流程推动，说服效果一般；面对利益受损方时推动力下降。",
     "命令式或情绪化施压；推不动就绕道、抱怨或放弃。",
     "说服时是否引用对方关切；是否给反对者留台阶。",
     "讲一次你成功说服反对你的人支持方案的经历。你怎么找到他真正在意的点？", 3.0),
    ("team", "协作补位", 11, "C",
     "主动补位且边界清晰；不抢功也不甩锅，团队协作成本低。",
     "配合度高但被动，等指派；补位时边界表达偏软，容易被默认为默认承接。",
     "边界模糊导致他人无法预期，或遇事推诿、抢功。",
     "补位时是否同步说清代价与归属；功劳表述方式。",
     "讲一次你主动接过不属于自己职责的事，或你明确拒绝了一次不合理要求。", 3.6),
]

# 对外 4 维度（对外只报 4 个，分量表只进教练版）
OUTER = [
    ("A", "情绪自控", "自我觉察 + 情绪稳定", "压力下不被情绪带走，能识别自己的触发点并调整行为", 25),
    ("B", "同理沟通", "同理心 + 倾听表达", "读得懂对方情绪与潜台词，也让对方接得住自己的话", 25),
    ("C", "冲突与协作", "冲突处理 + 协作补位", "分歧摆到台面上，协作时能补位也守得住边界", 25),
    ("D", "关系与影响", "关系经营 + 影响力说服", "三条线关系都可用，能把人和事一起推得动", 25),
]

P50 = {"self": 2.7, "regu": 2.6, "empa": 2.8, "comm": 2.9, "conf": 2.7, "rela": 2.9, "infl": 2.7, "team": 3.0}
PASS_LINE = 3.0      # 岗位合格线（0–5 制），与集团称职度「加权分≥3.0」同口径
COLLAPSE = 2.0       # 单维塌陷线：低于 2 分直接判不行

ORDER = ["regu", "conf", "rela", "infl", "empa", "team", "comm", "self"]
RANK = {k: i + 1 for i, k in enumerate(ORDER)}
W = {d[0]: d[2] for d in DIMS}
S = {d[0]: d[9] for d in DIMS}
idx = {d[0]: i for i, d in enumerate(DIMS)}

def pct(x):
    return round(x / 5 * 100, 1)

weighted = sum(W[k] * S[k] for k in W) / 100.0
overall = round(weighted, 2)

OUTER_SCORE = {}
for code, name, subs, desc, w in OUTER:
    keys = [d[0] for d in DIMS if d[3] == code]
    OUTER_SCORE[code] = round(sum(S[k] for k in keys) / len(keys), 2)

def band(v):
    if v >= 4.0: return "优势区", "good", "可授权：能带教他人、处理复杂关系"
    if v >= 3.4: return "稳健区", "good", "达标且有余量：可独立承担"
    if v >= 3.0: return "达标区", "neu", "达标：按岗位常规授权"
    if v >= 2.4: return "带教区", "sand", "低于合格线：须列入带教观察项"
    if v >= COLLAPSE: return "边缘区", "sand", "接近塌陷：带教不足以覆盖"
    return "风险区", "red", "塌陷：不建议进入关键协作岗位"

# ---------------- 蛛网图（inline SVG） ----------------
def radar_svg():
    n = len(DIMS)
    cx, cy, R = 520, 430, 300
    ordered = [DIMS[idx[k]] for k in ORDER]
    labels = [d[1] for d in ordered]
    scores = [d[9] for d in ordered]
    weights = [d[2] for d in ordered]
    p50 = [P50[d[0]] for d in ordered]
    outer_code = [d[3] for d in ordered]

    def pt(i, val, r=None):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        rr = R * (val / 5.0) if r is None else r
        return (cx + rr * math.cos(ang), cy + rr * math.sin(ang))

    o = ['<svg viewBox="0 0 1040 900" class="radar" role="img" aria-label="情商八维能力蛛网图">']
    for ring in range(1, 6):
        pts = " ".join("%.1f,%.1f" % pt(i, ring) for i in range(n))
        o.append('<polygon points="%s" fill="none" stroke="#DCE4DF" stroke-width="1"/>' % pts)
    for i in range(n):
        x, y = pt(i, 5)
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#E6EAE7" stroke-width="1"/>' % (cx, cy, x, y))
    for v in (1, 3, 5):
        o.append('<text x="%.1f" y="%.1f" font-size="12" fill="#9AA8A1" text-anchor="end">%d</text>' % (cx - 12, cy - R * v / 5.0 + 5, v))
    pts = " ".join("%.1f,%.1f" % pt(i, PASS_LINE) for i in range(n))
    o.append('<polygon points="%s" fill="none" stroke="#C0453B" stroke-width="1.7" stroke-dasharray="6 4"/>' % pts)
    pts = " ".join("%.1f,%.1f" % pt(i, p50[i]) for i in range(n))
    o.append('<polygon points="%s" fill="#3D7A5B" fill-opacity="0.08" stroke="#3D7A5B" stroke-width="1.4" stroke-dasharray="3 3"/>' % pts)
    pts = " ".join("%.1f,%.1f" % pt(i, scores[i]) for i in range(n))
    o.append('<polygon points="%s" fill="#C9A55C" fill-opacity="0.26" stroke="#B08A3C" stroke-width="2.4"/>' % pts)
    for i in range(n):
        x, y = pt(i, scores[i])
        o.append('<circle cx="%.1f" cy="%.1f" r="5.4" fill="#B08A3C" stroke="#fff" stroke-width="2"/>' % (x, y))
    for i in range(n):
        x, y = pt(i, 5, R + 66)
        ang = -math.pi / 2 + 2 * math.pi * i / n
        anchor = "middle"
        if math.cos(ang) > 0.35: anchor = "start"
        elif math.cos(ang) < -0.35: anchor = "end"
        o.append('<text x="%.1f" y="%.1f" font-size="19" font-weight="700" fill="#1D2A23" text-anchor="%s">%s</text>' % (x, y - 6, anchor, labels[i]))
        o.append('<text x="%.1f" y="%.1f" font-size="14" fill="#6B7C74" text-anchor="%s">%.1f 分 · %s</text>' % (x, y + 16, anchor, scores[i], outer_code[i]))
    o.append('<g transform="translate(96,848)">')
    ox = 0
    for c, t, w, dash in [("#B08A3C", "候选人得分（示例数据）", 2.4, ""), ("#C0453B", "岗位合格线 3.0 分", 1.7, "6 4"), ("#3D7A5B", "同类岗位在岗者 P50", 1.4, "3 3")]:
        da = ' stroke-dasharray="%s"' % dash if dash else ""
        o.append('<line x1="%d" y1="0" x2="%d" y2="0" stroke="%s" stroke-width="%.1f"%s/>' % (ox, ox + 34, c, w, da))
        o.append('<text x="%d" y="5" font-size="15" fill="#42544B">%s</text>' % (ox + 44, t))
        ox += 44 + len(t) * 15 + 30
    o.append('</g></svg>')
    return "\n".join(o)

# ---------------- 单项分析文案 ----------------
ANALYSIS = {
 "self": dict(
   strength="能识别自己的情绪触发点，复盘语言具体（「听到对方质疑业绩的第一秒，我其实想的是证明自己没错」），不把问题往外推。",
   risk="需要别人先说出他哪里不舒服才反应过来；自评与实际给他人造成的压力之间存在盲区。",
   scene_u="新带团队时能提前识别自己的管理风格偏移，避免把「追责」当成「跟进」。",
   scene_r="面对强刺激场景（上级当众批评、客诉升级），情绪识别一旦滞后，反应强度会明显放大。",
   action="入职 30 天内做一次「情绪触发点自述清单」，由直属上级每月对照一次。",
   verdict="先识别后调整，属于可发展的基础项，不是天花板。"),
 "regu": dict(
   strength="高压下输出稳定，被质疑后不迁怒、不冷处理；事后不把情绪带进后续协作。",
   risk="情绪外溢后习惯自我合理化（「我是为他们好」），同事反馈会被当成外行意见。",
   scene_u="大型活动开园、节假日集中客诉、突发舆情当天的现场指挥，是最能看出差距的场景。",
   scene_r="长期高压岗位（招商、客服、运营一线）下稳定性会衰减，需要提前建支持机制。",
   action="入职 60 天内做一次「高压事件复盘」：事件—当时反应—下次动作。",
   verdict="本项为核心维度，直接决定能不能授权。"),
 "empa": dict(
   strength="能同时看到对方的诉求和情绪，读得出「没说出口的那部分」，并且愿意为对方调整做法。",
   risk="对陌生群体（游客、供应商、加盟方）的情绪读解偏弱，容易把情绪化表达直接归类为「不专业」。",
   scene_u="游客投诉、同行恶性比价、跨机构（景区/酒店/营销）利益协调时，同理心是化解误会的第一道成本。",
   scene_r="面对高情绪、高对抗的外部方，先共情后解决可省掉一半的沟通回合。",
   action="培训重点放「情绪—诉求」分离话术，纳入新人首月复盘。",
   verdict="共情不等于让步，这项要看后续是否落到具体行动。"),
 "comm": dict(
   strength="复述他人观点准确，表达有结构；对方能自然接得住话头。",
   risk="在信息量大的场景里复述有偏差，容易变成「各自理解」，把沟通成本转嫁到后面的执行。",
   scene_u="跨机构会议、多方拉群对齐进度时，表达要能落到「谁、做什么、什么时候」三要素。",
   scene_r="向上汇报时若结构不清，会被解读为「思路不清」而不是「讲得急」。",
   action="所有关键沟通留书面纪要（结论/责任人/时间），一周后回看是否有理解偏差。",
   verdict="该项是能力基本盘，反馈频次高、改进快。"),
 "conf": dict(
   strength="愿意把分歧摆到台面上，冲突后合作效率不下降。",
   risk="公开或跨部门场景下倾向回避与拖延，私下解决后再把情绪带到流程里；分歧解决成本高。",
   scene_u="文旅场景里多方目标不一致（营销冲量与运营保体验、集团指标与机构利润）几乎天天出现，冲突处理是日常消耗项。",
   scene_r="回避型处理短期看不出问题，一旦涉及利益分配会被集中引爆。",
   action="入职 90 天内主动做一次「分歧当面对齐」，由上级陪跑一次并留书面纪要。",
   verdict="本项为核心维度，短板可带教，但必须列入 90 天观察项并设专人跟进。"),
 "rela": dict(
   strength="与上级、平级、下属三条线都有可用信任，会主动经营而不是等事情找到自己。",
   risk="关系维护偏被动，跨机构合作主要靠流程与上级推动，个人号召力尚未验证。",
   scene_u="需要横向借力（借人手、借场地、借渠道）时，这一项直接决定推动效率。",
   scene_r="关系与立场绑定时，组织调整期会迅速失去杠杆。",
   action="入职 90 天内盘点关键关系（8–12 人）并各自建立一次非事务性沟通。",
   verdict="属于可积累项，看 3 个月后的曲线比看当下分数更准。"),
 "infl": dict(
   strength="能摆事实、讲对方在意的点，在有反对意见时仍能把事推下去。",
   risk="说服路径偏「流程＋职级」，面对真正的反对者（利益受损方、能力强但不认同的人）推动力下降。",
   scene_u="推跨部门排期、争取资源、说服业主与商户配合，取决于这一项。",
   scene_r="授权型岗位如果只会用权力不用说服，团队会形成「只听领导」的汇报习惯。",
   action="把一次关键说服做成复盘样本：对象、顾虑、我怎么改的。",
   verdict="说服力无法靠培训速成，需在真实项目里验证。"),
 "team": dict(
   strength="主动补位且把边界说清楚，不抢功也不甩锅，团队协作成本低。",
   risk="补位时边界表达偏软，容易被默认为默认承接，长期造成隐形负担。",
   scene_u="景区一线旺季、突发事件中，「谁先上」决定服务质量下限。",
   scene_r="边界不清的候选人在多机构环境中会制造隐性分工争议。",
   action="入职 30 天内与上级确认「哪些事默认接、哪些必须先问」。",
   verdict="协作意愿强，边界管理是其进阶点。"),
}
STRONG = {"self": "基础项，影响上限而非下限", "regu": "核心维度，决定能否授权",
          "empa": "文旅服务场景投入产出比最高", "comm": "能力基本盘，改进快",
          "conf": "核心维度，短板须列观察清单", "rela": "可积累项，看 3 个月曲线",
          "infl": "无法速成，需真实项目验证", "team": "意愿强，边界管理是进阶点"}

# ---------------- 题型模块（调研口径） ----------------
DEEP = [
    ("0 岗位胜任力映射", "HR + 业务负责人前置共创", "4 小时（准备期）", "—", "4 个对外维度 + 每维 3–5 条可观察行为", "不映射到岗位行为的维度不测"),
    ("1 EQ 自评（可选）", "中文版 WLEIS-C 16 题（7 级）／采购 MHS EQ-i 2.0 全量 133 题", "20–30 分钟", "≤5%（仅生成假设，不计淘汰）", "自我觉察", "自评只与行为面做差值分析；EQ-i 2.0 官方分数不与外部常模混用"),
    ("2 SJT 情境判断", "情境 + 4 选 1，分维度计分", "30–40 分钟", "30%", "冲突处理、关系经营、同理心", "抗伪装：CR-retest——先写一句「我会怎么做」，再答闭合选项，效果优于考前警告语"),
    ("3 结构化行为面 + BARS", "3 名评委（HR／用人经理／跨部门）独立打分", "40–50 分钟", "35%", "全部维度", "锚点写可观察行为，禁「善于沟通」式形容词；一致率 ICC(2,k) ≥ 0.70"),
    ("4 小组任务", "无领导小组 / 角色扮演 / 桌面推演", "60 分钟 + 30 分钟讲评", "25%", "冲突处理、影响力、协作补位", "锚点表预先发布；只观察不引导，记录边界语言"),
    ("5 压力情景", "追问式压力面谈（含打断与质疑）", "10–15 分钟", "5–10%", "情绪稳定", "只做「可接受／不可接受」二分，不追问隐私"),
    ("6 汇判", "先各自交分，再讨论；输出证据条数", "30 分钟", "—", "全部维度", "不设单一分数线自动淘汰，由证据条数与规则共同定档"),
]
COMPACT = [
    ("快筛版", "25 分钟", "SJT 20 题 + 5 分钟压力面谈", "批量初筛，一次筛掉明显不合格者", "只输出「进入深度测试 / 淘汰」"),
    ("招聘压缩版（本方案默认）", "90 分钟", "自评 10 + SJT 15 + 行为面 30 + 压力面谈 15 + 汇判 10（小组任务按岗位选配）", "常规岗位终面，出蛛网图 + 单项分析 + 带教建议", "完整呈现格式 + 行 / 不行结论"),
    ("深度选拔版", "约 3.5–4 小时", "调研推荐全套（自评→SJT→行为面→小组→压力→汇判）", "管培、储备干部、高管选拔", "加小组任务与讲评，输出教练版画像"),
    ("复核版", "30 分钟", "只补测低于合格线的 1–2 个维度", "对带教区维度做二次取证", "不重新计总分，只决定该项档位"),
]
MAPPING = [
    ("Goleman 混合模型（1995 至今最通行）", "五域：自我觉察／自我管理／社会意识（同理心）／关系管理／内在动机",
     "自我觉察、情绪稳定、同理心、倾听表达、冲突处理、关系经营、影响力说服", "中文实务与培训的事实标准；四分支口径也出自此处"),
    ("Mayer–Salovey 能力模型", "四分支：感知／运用／理解／管理情绪", "SJT 题型分层", "把 EQ 定义为「对情绪信息做准确推理并运用的能力」，可测上限"),
    ("Bar-On EQ-i（底本）", "五域：内省／人际／压力管理／适应力／一般心境", "情绪稳定、压力情景设计", "条式测量底本；「Barron EQ 4C」未见公开来源，本方案不引用"),
    ("EQ-i 2.0（MHS，2011）", "133 题、15 分量表 + 5 合成分（自我知觉／自我表达／自我管理／社会意识／关系管理）、常模 4000 人",
     "仅作自评参照系", "唯一带完整常模与效度指标的商用品，需认证方能购买解读；「40 题四分支版」非官方产品，勿对外引用"),
    ("中文职场实务结构（情绪认知／情绪调节／情绪运用 + 关系管理／冲突处理／压力管理／责任感／同理心／社交技能／影响力）",
     "8 个子项", "本方案 8 维骨架", "实务中多为跨框架拼装，无单一权威中文量表；有中文信效度研究的是 WLEIS-C 四维版"),
]
SJT = [
    ("S-03", "同理心", "下属在群里公开质疑你的排期安排，语气生硬。多数同事选择不接话，你更可能：",
     ["A. 先私下找他，问是不是自己没讲清楚，把可能的误会先摆平",
      "B. 在群里直接说明排期依据，把话说清楚，避免他继续被误解",
      "C. 暂不回应，等他冷静后再说，免得激化",
      "D. 请上级出面处理，表示自己没有管理能力"],
     "A 计 2 分 / B 计 1 分 / C 计 0 分 / D 计 0 分", "选 C 记「回避型」，选 D 记「授权外移」；两选出现时该维度不得高于 3 分"),
    ("S-07", "冲突处理", "你和同级负责人在同一活动上争资源，邮件已来回三轮，对方明显不耐烦。你的做法是：",
     ["A. 继续邮件，把数据补得更全，辩到底",
      "B. 打电话或当面谈，先确认对方的真实顾虑，再谈可行方案",
      "C. 把双方都拉进群，让上级决定",
      "D. 放弃这块资源，避免影响关系"],
     "B 计 2 分 / A 计 1 分 / C 计 0 分 / D 计 0 分", "选 C 记「向上转移」；选 D 记「关系优先于问题」"),
    ("S-11", "情绪稳定", "开园前 2 小时，你负责的检票环节被游客围住投诉，同事在旁边手足无措。你：",
     ["A. 先接管现场分流，同时安排同事去处理投诉，让事情先动起来",
      "B. 让同事继续顶着，自己先把投诉处理完",
      "C. 先安抚同事情绪，避免他慌了出错",
      "D. 立刻上报领导，等指示"],
     "A 计 2 分 / B 计 1 分 / C 计 1 分 / D 计 0 分", "选 C 若伴随情绪化表达，则本项不得高于 3 分"),
    ("S-15", "关系经营", "一位合作过两次的机构负责人半年没联系，这次找到你办事。你：",
     ["A. 直接看能不能办，能办就办，不办就说明原因",
      "B. 先问候并回顾上次合作的细节，确认对方近况后再谈事",
      "C. 转给同事对接，自己不介入",
      "D. 先找其他同事打听一下对方最近的情况"],
     "B 计 2 分 / A 计 1 分 / C 计 0 分 / D 计 0 分", "选 D 记「交易性关系」倾向"),
    ("S-18", "影响力说服", "你提的排期方案被负责经营的两名负责人同时反对，理由是影响收入。你最可能：",
     ["A. 强调公司要求与制度刚性，让对方必须执行",
      "B. 拿出过往同场景数据，找到收入影响最小的替代方案请他们选",
      "C. 私下分别沟通，了解各自反对的真实原因",
      "D. 换个话题，等他们自己想通"],
     "B 或 C 计 2 分 / A 计 1 分 / D 计 0 分", "选 A 若伴随情绪施压，则本 项不得高于 3 分"),
    ("S-22", "协作补位", "同一项目里同事临时请假，他手上有一项和你冲突的交付。你的处理：",
     ["A. 先接下，同时明确告诉他回来后怎么交接",
      "B. 直接接下，先不说，等他回来再说",
      "C. 找第三方判断该不该接",
      "D. 明确说自己手上的事更急，不接"],
     "A 计 2 分 / B 计 1 分 / C 计 0 分 / D 计 0 分", "选 B 记「边界模糊」；选 D 记「边界偏硬」，需追问是否有协商过程"),
]
PRIN = [
    ("行为锚定，不贴标签", "只评与岗位相关、可观察到的行为，不评人格类型；输出写「在 X 情境下倾向 Y 行为」，不写「情商低」。"),
    ("自评只当假设", "应聘场景下自评伪装效应显著（模拟求职 d=1.47、他评 d=1.56），且伪装会改变排序，因此自评不计分，只用于生成待验证假设。"),
    ("多方法交叉验证", "SJT、行为面、小组任务、压力情景四路证据一致才下结论；单来源不作结论。"),
    ("同一把尺", "8 维共用 0–5 锚定尺（0/3/5 三档），锚点写可观察行为；评委培训后独立打分，分歧 >1 分必须回原始证据复核。"),
    ("依据栏写事实", "沿用集团既有评分纪律：每条评分写事实与候选人原话，不写形容词；无证据的分数不计入合议。"),
    ("红线只触发复核", "诚信与责任类问题先触发复核与补证，复核确认后才影响结论；测评结果不作为录用唯一依据。"),
]
FLOW = [
    ("STEP 00", "知情同意", "提前告知测试目的、谁看结果、留存期限、拒绝不影响录用；候选人签署后施测。", "测评前"),
    ("STEP 01", "岗位画像定权重", "按岗位序列确定对外 4 维度与 8 子维权重、红线口径；管理岗加大协作与影响力，服务岗加大同理心与倾听。", "测评前 3 天"),
    ("STEP 02", "出题与锚定表校准", "从题库抽题并改写成本岗位情境；用 2–3 个样例做评委试标，一致率不达标先改题不改人。", "测评前 5 天"),
    ("STEP 03", "评委培训（60 分钟）", "统一 0–5 锚点含义、取证追问方式、禁止标签化表述；现场试标一致率需达 ICC(2,k) ≥ 0.70。", "测评当天前"),
    ("STEP 04", "施测", "先自评（降防御）→ SJT → 行为面 → 小组 → 压力情景收尾；每段先各自打分再讨论。", "测评当天"),
    ("STEP 05", "证据复核与汇判", "分歧 >1 分回原始记录；红线项单独评审；生成蛛网图与单项分析，输出证据条数而非印象分。", "次日"),
    ("STEP 06", "结果交付与回访", "向候选人反馈体验与结果口径；背景调查重点回访红线项与关键短板项；原始记录留存不超过 1 年。", "5 个工作日内"),
    ("STEP 07", "入职后复测", "90 天复评同一套维度，比对入职前后曲线；偏差大的候选人进入校准样本。", "入职 90 天"),
]
ONE_LINE = {"regu": "压力下稳得住，是当前最稳的资产", "conf": "分歧面前偏回避，是唯一明确缺口",
            "rela": "三条线关系都可用，横向借力没问题", "infl": "能推动但偏流程，说服力待验证",
            "empa": "读得出情绪，服务场景优势明显", "team": "补位主动且边界清楚，协作成本低",
            "comm": "表达结构尚可，复述偶有偏差", "self": "有复盘意识，触发点描述偏笼统"}
CONS = {"regu": "高（4/4）", "conf": "中（3/4）", "rela": "高（4/4）", "infl": "高（4/4）",
        "empa": "高（4/4）", "team": "高（4/4）", "comm": "中（3/4）", "self": "低（2/4）"}
SRC = [
    ("EQ-i 2.0 官方手册（MHS）：133 题、15 分量表、5 合成分、常模与效度指标", "https://cdn.mhs.com/mhsdocs/EQi20Manual/part1/Intro.html"),
    ("伪装效应：模拟求职指令下自评 d=1.47、他评 d=1.56，伪装改变排序", "https://pmc.ncbi.nlm.nih.gov/articles/PMC11134977/"),
    ("抗伪装：CR-retest（先写方案再答闭合项）优于考前警告语（d=−0.22）", "https://bs.ustc.edu.cn/pub/file/20260409/17757037488095350.pdf"),
    ("40 种情绪智力测量工具结构与信效度总表（Bru-Luna et al., 2021）", "https://pmc.ncbi.nlm.nih.gov/articles/PMC8701889/"),
    ("SJT 最佳实践建议（Lievens）", "https://www.cambridge.org/core/journals/australasian-journal-of-organisational-psychology/article/abs/best-practice-recommendations-for-situational-judgment-tests/826822D81D798B88CAC592F907C3EADB"),
    ("中国大陆：性格测试作录用硬指标涉嫌就业歧视（人民法院报 2025-07-26）", "https://www.chinacourt.cn/article/detail/2025/07/id/8918037.shtml"),
    ("GB/T 45253-2025《互联网心理服务 心理测评服务通用规范》（2025-02-28 实施）", "https://std.samr.gov.cn/gb/search/gbDetailed?id=2FF37940EB39D753E06397BE0A0A413F"),
    ("中文情绪智力综述（陈猛等，2012，《心理科学进展》20(3):412-423）", "https://journal.psych.ac.cn/xlkxjz/CN/Y2012/V20/I3/412"),
]

# ---------------- HTML ----------------
def build_html():
    h = []; a = h.append
    a('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">')
    a('<meta name="viewport" content="width=1560">')
    a('<title>候选人测试二 · 情商与关系管理测试（EQ Test）</title>')
    a('<style>')
    a('''
    *{margin:0;padding:0;box-sizing:border-box}
    :root{
      --green:#1E4634;--green2:#2A5C42;--green3:#3D7A5B;--gold:#C9A55C;--cream:#F5F0E4;
      --paper:#FAF9F4;--ink:#1D2A23;--ink2:#42544B;--muted:#77867D;--line:#E6EAE7;
      --red:#C0453B;--red-bg:#FBEDEA;--good:#1B7A56;--good-bg:#E5F1EB;--neu:#4C5C55;--neu-bg:#EFF3F0;
      --sand:#8A7448;--sand-bg:#F4EEE0;
    }
    html,body{background:var(--paper)}
    body{width:1560px;font-family:"PingFang SC","Hiragino Sans GB","Heiti SC","Microsoft YaHei",system-ui,sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased}
    .hero{position:relative;overflow:hidden;padding:40px 54px 38px;background:radial-gradient(1100px 320px at 88% -60%,rgba(255,255,255,.13),transparent 62%),radial-gradient(760px 300px at 4% 130%,rgba(201,165,92,.18),transparent 60%),linear-gradient(112deg,#183C2C 0%,#1E4634 42%,#2C6146 100%);color:#fff}
    .hero::after{content:"";position:absolute;inset:0;background-image:repeating-linear-gradient(115deg,rgba(255,255,255,.028) 0 1px,transparent 1px 62px);pointer-events:none}
    .hero-row{display:flex;align-items:flex-end;justify-content:space-between;gap:30px;position:relative;z-index:2}
    .title-wrap{display:flex;align-items:center;gap:18px}
    .bar{width:7px;height:62px;border-radius:4px;background:linear-gradient(180deg,var(--gold),#E7D4A8);flex:none}
    h1{font-size:45px;letter-spacing:.045em;font-weight:800;line-height:1.12}
    .sub{margin-top:10px;font-size:16px;color:rgba(255,255,255,.72);letter-spacing:.06em}
    .datechip{flex:none;text-align:center;padding:12px 26px;border-radius:16px;background:rgba(255,255,255,.11);border:1px solid rgba(255,255,255,.24)}
    .datechip .d1{font-size:13px;color:rgba(255,255,255,.66);letter-spacing:.14em}
    .datechip .d2{font-size:26px;font-weight:700;letter-spacing:.03em;margin-top:4px}
    .goldline{height:4px;background:linear-gradient(90deg,var(--gold) 0%,#E4D3AC 34%,var(--cream) 62%,rgba(245,240,228,.25) 100%)}
    .body{padding:30px 54px 40px}
    .sec{margin-bottom:34px}
    .sec-h{display:flex;align-items:flex-end;gap:14px;margin-bottom:16px;border-bottom:2px solid var(--green);padding-bottom:9px}
    .sec-h .no{font-size:13px;font-weight:800;letter-spacing:.16em;color:var(--gold);border:1px solid var(--gold);border-radius:6px;padding:3px 9px}
    .sec-h h2{font-size:25px;font-weight:800;letter-spacing:.02em}
    .sec-h .note{margin-left:auto;font-size:13px;color:var(--muted)}
    .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:8px}
    .kpi{background:#fff;border:1px solid var(--line);border-left:4px solid var(--green);border-radius:12px;padding:16px 18px}
    .kpi .k{font-size:29px;font-weight:800;color:var(--green);letter-spacing:.01em}
    .kpi .l{font-size:14px;font-weight:700;margin-top:2px}
    .kpi .d{font-size:12.5px;color:var(--muted);margin-top:6px;line-height:1.6}
    .card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px 22px}
    .lead{font-size:15.5px;line-height:1.95;color:var(--ink2)}
    .lead b{color:var(--ink)}
    .callout{border-left:4px solid var(--gold);background:var(--cream);border-radius:0 12px 12px 0;padding:14px 18px;font-size:14.5px;line-height:1.85;color:var(--ink2)}
    .callout b{color:var(--green)}
    .warn{border-left:4px solid var(--red);background:var(--red-bg);border-radius:0 12px 12px 0;padding:14px 18px;font-size:14.5px;line-height:1.85;color:#7A2B24}
    .warn b{color:var(--red)}
    table{width:100%;border-collapse:collapse;font-size:14px}
    th{background:var(--green);color:#fff;text-align:left;padding:10px 12px;font-weight:700;font-size:13.5px;letter-spacing:.03em}
    td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top;line-height:1.75;color:var(--ink2)}
    tr:nth-child(even) td{background:#FCFBF8}
    td b{color:var(--ink)}
    .tw{background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden}
    .tag{display:inline-block;padding:2px 9px;border-radius:20px;font-size:12px;font-weight:700;white-space:nowrap}
    .t-good{background:var(--good-bg);color:var(--good)}
    .t-neu{background:var(--neu-bg);color:var(--neu)}
    .t-sand{background:var(--sand-bg);color:var(--sand)}
    .t-red{background:var(--red-bg);color:var(--red)}
    .t-gold{background:#F6EFDD;color:#8A6C2E}
    .twocol{display:grid;grid-template-columns:1fr 1fr;gap:16px}
    .radar-wrap{display:grid;grid-template-columns:1.32fr 1fr;gap:18px}
    .radar{width:100%;height:auto;display:block}
    .legend-note{font-size:13px;color:var(--muted);line-height:1.85}
    .dim{border:1px solid var(--line);border-radius:14px;background:#fff;margin-bottom:14px;overflow:hidden}
    .dim-h{display:flex;align-items:center;gap:14px;padding:13px 20px;background:linear-gradient(96deg,#F7F4EC,#fff);border-bottom:1px solid var(--line)}
    .dim-h .no{width:34px;height:34px;border-radius:9px;background:var(--green);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:15px;flex:none}
    .dim-h .nm{font-size:19px;font-weight:800}
    .dim-h .wt{font-size:12.5px;color:var(--muted);margin-left:2px}
    .dim-h .sc{margin-left:auto;display:flex;align-items:center;gap:12px}
    .dim-h .sc .num{font-size:26px;font-weight:800;color:var(--green)}
    .dim-h .sc .num small{font-size:13px;color:var(--muted);font-weight:600}
    .dim-b{display:grid;grid-template-columns:1fr 1fr;gap:0}
    .dim-b>div{padding:14px 20px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
    .dim-b>div:nth-child(2n){border-right:none}
    .dim-b .lb{font-size:12px;font-weight:800;letter-spacing:.12em;color:var(--gold);margin-bottom:6px}
    .dim-b p{font-size:14px;line-height:1.85;color:var(--ink2)}
    .dim-b .full{grid-column:1 / -1;border-right:none}
    .quote{background:var(--cream);border-radius:10px;padding:12px 14px;font-size:14px;line-height:1.85;color:#4A3F26;border-left:3px solid var(--gold)}
    .quote .q{color:var(--muted);font-size:12.5px;display:block;margin-top:5px}
    .flow{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
    .step{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px}
    .step .sn{font-size:12px;font-weight:800;color:var(--gold);letter-spacing:.14em}
    .step .st{font-size:15.5px;font-weight:800;margin:5px 0 6px}
    .step p{font-size:13px;line-height:1.8;color:var(--ink2)}
    .step .when{margin-top:8px;font-size:12px;color:var(--muted)}
    .verdict{display:grid;grid-template-columns:1.1fr 1fr 1fr;gap:14px}
    .vd{border-radius:14px;padding:18px 20px;border:1px solid var(--line);background:#fff}
    .vd.win{border-top:5px solid var(--good)}
    .vd.cond{border-top:5px solid var(--sand)}
    .vd.lose{border-top:5px solid var(--red)}
    .vd h4{font-size:18px;margin-bottom:8px}
    .vd ul{margin-left:16px;font-size:13.5px;line-height:1.85;color:var(--ink2)}
    .foot{margin-top:26px;padding-top:16px;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted);line-height:1.9}
    .outer{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
    .oc{background:#fff;border:1px solid var(--line);border-top:5px solid var(--green);border-radius:14px;padding:16px 18px}
    .oc .code{font-size:12px;font-weight:800;letter-spacing:.16em;color:var(--gold)}
    .oc h4{font-size:19px;margin:4px 0 4px}
    .oc .subs{font-size:12.5px;color:var(--muted);margin-bottom:8px}
    .oc .score{font-size:30px;font-weight:800;color:var(--green)}
    .oc .score small{font-size:13px;color:var(--muted);font-weight:600}
    .oc p{font-size:13px;line-height:1.8;color:var(--ink2);margin-top:6px}
    .srclist{font-size:12.5px;color:var(--muted);line-height:1.9}
    .srclist a{color:#3D7A5B;word-break:break-all}
    ''')
    a('</style></head><body>')

    # Hero
    a('<div class="hero"><div class="hero-row">')
    a('<div class="title-wrap"><div class="bar"></div><div><h1>候选人测试二 · 情商与关系管理测试</h1>'
      '<div class="sub">EQ &amp; RELATIONSHIP TEST ｜ 设计框架 · 评分体系 · 蛛网图呈现 · 单项分析</div></div></div>')
    a('<div class="datechip"><div class="d1">方案版本</div><div class="d2">V1.0</div>'
      '<div class="d1" style="margin-top:4px">2026-10-24</div></div>')
    a('</div></div><div class="goldline"></div>')
    a('<div class="body">')

    # 摘要
    kpis = [
        ("90 / 25 分钟", "压缩版 / 快筛版", "深度选拔版约 3.5–4 小时；本方案默认 90 分钟压缩版"),
        ("4 + 8 维", "对外维度 / 教练版明细", "对外只报 4 个 EQ 维度，8 个子维仅进教练版与蛛网图"),
        ("0–5 分制", "与既有口径一致", "锚定 0/3/5 三档；加权分 ≥ 3.0 且无维 < 2 → 行"),
        ("自评仅假设", "抗伪装的硬约束", "应聘场景自评伪装 d=1.47，自评不计分，只与行为面做差值"),
    ]
    a('<div class="sec"><div class="sec-h"><span class="no">摘要</span><h2>一页看懂这项测试</h2>'
      '<span class="note">集团行政人事部</span></div>')
    a('<div class="kpis">')
    for k, l, d in kpis:
        a('<div class="kpi"><div class="k">%s</div><div class="l">%s</div><div class="d">%s</div></div>' % (k, l, d))
    a('</div>')
    a('<div class="card" style="margin-top:14px"><p class="lead">'
      '本测试是候选人评估中的<b>第二项测试</b>，专门测<b>情商</b>——一个人在被冒犯、被误解、被施压、被反对时，'
      '还能不能把事办成、把关系留住、把话说到位。它不测性格标签（不是「你是内向还是外向」），'
      '而是测<b>在可复现的管理情境下的典型反应</b>。<br>'
      '框架取市面上最主流的三套结构交叉验证：<b>Goleman 情绪智力五域</b>（能力骨架）、'
      '<b>Mayer–Salovey 四分支</b>（题型分层：感知→理解→管理→运用）、'
      '<b>EQ-i 2.0 与 Bar-On EQ-i</b>（工具参照），并按集团文旅多机构协同的实际场景做了增补。'
      '落到<b>对外 4 个 EQ 维度、教练版 8 个子维 + 1 条诚信责任红线</b>，用同一把 0–5 锚定量表打分，'
      '结果以<b>蛛网图直观呈现</b>，再逐项做行为解读、取证追问与落地建议；'
      '结论口径与集团既有称职度评估保持一致，仍回到<b>行 / 不行</b>。</p>'
      '<p class="legend-note" style="margin-top:10px">本页模型与工具口径依据同日完成的调研简报《EQ测评调研简报_2026-10-24.md》'
      '（一手来源见附录二）；分数与判读文字为示例数据。</p></div>')
    a('</div>')

    # 一 定位
    a('<div class="sec"><div class="sec-h"><span class="no">一</span><h2>测试定位：它在整个评估里承担什么</h2>'
      '<span class="note">既有三维度框架不变</span></div>')
    a('<div class="twocol">')
    a('<div class="card"><p class="lead"><b>既有评估框架（不变）：</b>专业技能、管理技能、发展潜力三个维度，'
      '权重各 33%，结论口径为「行 / 不行」。<b>本测试不新增维度、不改权重</b>，'
      '它作为独立的一项测试存在，同时为其中<b>两个维度提供关键证据</b>：'
      '管理技能（协同、冲突、带教）与发展潜力（抗压、可塑性、学习意愿）。</p>'
      '<div class="callout" style="margin-top:14px"><b>为什么单独设一项而不是并进面谈：</b>'
      '管理技能在常规面试里最容易被「故事讲得好」掩盖。情商的真实差异只在<b>压力、冒犯、反对</b>这三类情境下才暴露；'
      '单列成标准化测试，才能保证不同候选人、不同评委、不同岗位之间可比。</div></div>')
    a('<div class="card"><p class="lead"><b>测试要回答的三个问题：</b></p>'
      '<ul style="margin:10px 0 0 18px;font-size:14.5px;line-height:2;color:var(--ink2)">'
      '<li><b>他被冒犯时会怎样</b>——情绪稳定与冲突处理；</li>'
      '<li><b>他能不能让对方舒服地听他说话</b>——同理心与倾听表达；</li>'
      '<li><b>他能不能把人和事一起推得动</b>——关系经营、协作补位与影响力说服。</li></ul>'
      '<div class="callout" style="margin-top:14px"><b>不测什么：</b>不测 IQ、不做性格类型与人格标签式结论、'
      '不测酒量与体力极限，<b>不使用 SCL-90、SAS、SDS 等临床心理量表</b>（临床量表不得用于招聘决策）。'
      '这些与用人结果无关，且容易引发合规争议。</div></div>')
    a('</div></div>')

    # 二 框架
    a('<div class="sec"><div class="sec-h"><span class="no">二</span><h2>设计框架：模型来源、题型配比、评分与判定</h2>'
      '<span class="note">参考市面主流做法</span></div>')
    a('<div class="card" style="margin-bottom:14px"><p class="lead" style="margin-bottom:10px"><b>六条设计原则</b></p>'
      '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">')
    for i, (t, d) in enumerate(PRIN):
        a('<div style="background:#F7F5EE;border-radius:10px;padding:12px 14px">'
          '<div style="font-size:14.5px;font-weight:800;color:var(--green)">%d. %s</div>'
          '<div style="font-size:13px;line-height:1.8;color:var(--ink2);margin-top:5px">%s</div></div>' % (i + 1, t, d))
    a('</div></div>')

    a('<div class="tw" style="margin-bottom:14px"><table><thead><tr>'
      '<th style="width:180px">模型 / 结构来源</th><th style="width:300px">原始维度</th>'
      '<th style="width:250px">本方案的处理</th><th>说明</th></tr></thead><tbody>')
    for m in MAPPING:
        a('<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td></tr>' % m)
    a('</tbody></table></div>')

    a('<div class="tw" style="margin-bottom:14px"><table><thead><tr>'
      '<th style="width:130px">环节</th><th style="width:280px">形式</th><th style="width:130px">时长</th>'
      '<th style="width:150px">权重</th><th style="width:180px">对应维度</th><th>采分与抗伪装设计</th>'
      '</tr></thead><tbody>')
    for d in DEEP:
        a('<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % d)
    a('</tbody></table></div>')

    a('<div class="tw" style="margin-bottom:14px"><table><thead><tr>'
      '<th style="width:180px">版本</th><th style="width:100px">时长</th><th style="width:340px">组成</th>'
      '<th style="width:220px">用途</th><th>输出物</th></tr></thead><tbody>')
    for q in COMPACT:
        a('<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % q)
    a('</tbody></table></div>')

    a('<div class="twocol">')
    a('<div class="card"><p class="lead"><b>评分与换算：</b>评委按 0–5 打分（5 分可授权、3 分达标、1 分不达标、0 分无有效行为证据），'
      '按维度权重加权得到总分（0–5 制）；同时给出百分制（×20）便于横向比较。<br>'
      '<b>一致性控制：</b>评委独立打分后再讨论（先各自交分）；同一维度评分差异 &gt;1 分必须回到原始证据复核；'
      'BARS 行为面通行门槛为 ICC(2,k) ≥ 0.60，本方案加严到 <b>0.70</b>，低于阈值先做锚定校准再施测。</p>'
      '<div class="callout" style="margin-top:12px"><b>抗伪装的三个硬手段：</b>'
      '① <b>CR-retest</b>：SJT 每题先让候选人写一句「我会怎么做」，再选闭合选项——'
      '研究显示其抑制分数膨胀的效果优于考前警告语（警告语 d=−0.22）；'
      '② <b>行为面与自评做差值</b>：两者背离超过 2 档即判「高自评低行为」，该维度不得高于 3 分；'
      '③ <b>三条证伪检查</b>：作答过快、同向全选最优选项、自评与行为证据互相矛盾。</div></div>')
    a('<div class="card"><p class="lead"><b>判定规则（与集团称职度评估同口径：加权分 + 单项下限）：</b></p>'
      '<div style="margin-top:8px"><table><thead><tr><th style="background:var(--good)">行</th>'
      '<th style="background:var(--sand)">有条件行</th><th style="background:var(--red)">不行</th></tr></thead><tbody>'
      '<tr><td>加权总分 ≥ 3.0（百分制 ≥ 60）<br>且 8 子维均 ≥ 2.0 分<br>且诚信责任红线复核未确认</td>'
      '<td>加权总分 2.4–3.0（百分制 48–60）<br>或存在子维落在 2.0–2.9 的带教区<br>'
      '→ 试岗 / 带教 90 天，第 90 天复评</td>'
      '<tr><td>加权总分 &lt; 2.4<br>或红线经复核确认<br>或任一子维 &lt; 2.0（塌陷）<br>'
      '或核心维度（情绪稳定 / 冲突处理）&lt; 2.0</td></tr></tbody></table></div>'
      '<p class="legend-note" style="margin-top:10px">核心维度 4 项：情绪稳定、冲突处理、关系经营、影响力说服，合计权重 58%；'
      '其中情绪稳定与冲突处理任一低于 2 分即触发淘汰，避免用关系经营类的长板掩盖冲突回避。'
      '总分高但单维塌陷的情形同样判「不行」——这是本方案专门加的一道防伪门。'
      '调研建议「不设单一分数线自动淘汰」，本方案的折中是：<b>不靠单一分数，要靠加权分 + 单项下限 + 红线 + 一致性门槛四要素共同定档</b>。</p></div>')
    a('</div></div>')

    # 三 维度锚定
    a('<div class="sec"><div class="sec-h"><span class="no">三</span><h2>维度定义与行为锚定（评委打分尺）</h2>'
      '<span class="note">0–5 制 · 5 / 3 / 1 三档锚点</span></div>')
    a('<div class="outer">')
    for code, name, subs, desc, w in OUTER:
        sc = OUTER_SCORE[code]
        bn, bc, bd = band(sc)
        a('<div class="oc"><div class="code">对外维度 %s · 权重 %d%%</div><h4>%s</h4>'
          '<div class="subs">＝ %s</div><div class="score">%.2f <small>/ 5.0</small></div>'
          '<div style="margin-top:6px"><span class="tag t-%s">%s</span></div>'
          '<p>%s</p></div>' % (code, w, name, subs, sc, bc, bn, desc))
    a('</div>')
    a('<div class="callout" style="margin-bottom:14px"><b>为什么对外只报 4 个维度：</b>'
      '维度过多会导致结论不可用——8 个子维只进教练版与蛛网图，对外结论与沟通只说 4 个维度，'
      '每个维度配 3–5 条可观察行为。</div>')
    for k in ORDER:
        d = DIMS[idx[k]]
        sc = d[9]
        bn, bc, bd = band(sc)
        oname = [o[1] for o in OUTER if o[0] == d[3]][0]
        a('<div class="dim"><div class="dim-h"><div class="no">%d</div>'
          '<div><span class="nm">%s</span><span class="wt">　权重 %d%%　对外维度 %s·%s</span></div>'
          '<div class="sc"><span class="tag t-%s">%s</span>'
          '<span class="num">%.1f <small>/ 5.0</small></span></div></div>'
          '<div class="dim-b">'
          '<div><div class="lb">5 分锚点（可授权）</div><p>%s</p></div>'
          '<div><div class="lb">1 分锚点（不达标）</div><p>%s</p></div>'
          '<div><div class="lb">3 分锚点（合格线）</div><p>%s</p></div>'
          '<div><div class="lb">观察信号</div><p>%s</p></div>'
          '<div><div class="lb">取证追问（可直接念）</div><p>%s</p></div>'
          '<div class="full"><div class="lb">本例读数</div>'
          '<p><b>%.1f 分</b>（百分制 %.0f 分），本档判断：%s；档位 <b>%s</b>。</p></div>'
          '</div></div>' % (RANK[k], d[1], d[2], d[3], oname, bc, bn, sc, d[4], d[6], d[5], d[7], d[8], sc, pct(sc), bd, bn))
    a('<div class="card" style="margin-top:4px"><p class="lead"><b>红线：诚信与责任（不参与加权，命中先触发复核）</b>　'
      '捏造履历或业绩数据；隐瞒对岗位有重大影响的信息；把责任推给不在场或弱势的一方；'
      '在利益面前反复失信；用不当方式获得荣誉或资源。<br>'
      '<span class="legend-note">按合规要求，红线<b>只触发复核</b>而非直接淘汰：必须写明事实依据与原话，'
      '经补充核查确认后才影响结论；不得以「感觉」「印象」定性，也不得默认不成立。</span></p></div>')
    a('</div>')

    # 四 蛛网图
    a('<div class="sec"><div class="sec-h"><span class="no">四</span><h2>结果直观呈现：八维蛛网图</h2>'
      '<span class="note">教练版明细 · 示例数据</span></div>')
    a('<div class="card"><div class="radar-wrap"><div>%s</div>'
      '<div><p class="lead" style="font-size:14.5px"><b>怎么读这张图</b></p>'
      '<ul style="margin:10px 0 0 18px;font-size:13.8px;line-height:1.95;color:var(--ink2)">'
      '<li><b>金色实线区域</b>＝候选人各子维得分（0–5 制），越靠外越强；</li>'
      '<li><b>红色虚线</b>＝岗位合格线 3.0 分，任一维落到红线以内即为该维未达岗位要求；</li>'
      '<li><b>绿色虚线带</b>＝同类岗位在岗者 P50（经验参照，不是绝对标准）；</li>'
      '<li>整体看<b>形状</b>不只看面积：面积大但某一维明显内凹，属<b>塌陷型</b>，按规则直接判「不行」。</li></ul>'
      '<div class="callout" style="margin-top:14px"><b>本例读数：</b>加权总分 <b>%.2f</b>（百分制 %.0f，合格线 3.0 / 60 分），'
      '8 子维中 1 维（冲突处理 2.4）落在合格线以内、但未到塌陷线，属「<b>加权过线但有单维缺口</b>」——'
      '按规则给出「<b>行，但须带教</b>」：入职后 90 天内以冲突处理为唯一重点带教项，'
      '指定直属上级每月复盘一次，第 90 天复评。</div>'
      '<p class="legend-note" style="margin-top:12px">数据来源说明：本页为<b>示例数据</b>，用于确认呈现格式与判定规则；'
      '正式使用时用实测分数替换，按同一脚本重新生成图与表格。</p></div></div></div>'
      % (radar_svg(), overall, pct(overall)))
    a('<div class="tw" style="margin-top:14px"><table><thead><tr><th style="width:60px">序</th><th style="width:130px">子维度</th>'
      '<th style="width:110px">对外维度</th><th style="width:70px">权重</th><th style="width:90px">得分</th>'
      '<th style="width:90px">百分制</th><th style="width:90px">贡献分</th><th style="width:100px">档位</th>'
      '<th style="width:110px">评委一致度</th><th>一句话判读</th></tr></thead><tbody>')
    for k in ORDER:
        d = DIMS[idx[k]]; sc = d[9]; bn, bc, bd = band(sc)
        oname = [o[1] for o in OUTER if o[0] == d[3]][0]
        a('<tr><td>%d</td><td><b>%s</b></td><td>%s</td><td>%d%%</td><td>%.1f</td><td>%.0f</td><td>%.2f</td>'
          '<td><span class="tag t-%s">%s</span></td><td>%s</td><td>%s</td></tr>'
          % (RANK[k], d[1], oname, d[2], sc, pct(sc), d[2] * sc / 100.0, bc, bn, CONS[k], ONE_LINE[k]))
    a('<tr><td colspan="5" style="text-align:right"><b>加权总分</b></td>'
      '<td><b>%.2f</b></td><td colspan="4"><b>合格线 3.0 分（百分制 60）· 结论：行（须带教）</b></td></tr>' % overall)
    a('</tbody></table></div>')
    a('</div>')

    # 五 单项分析
    a('<div class="sec"><div class="sec-h"><span class="no">五</span><h2>单项分析：逐维度行为解读与取证</h2>'
      '<span class="note">先读数 → 再行为 → 再取证 → 再动作</span></div>')
    for k in ORDER:
        d = DIMS[idx[k]]; sc = d[9]; an = ANALYSIS[k]; bn, bc, bd = band(sc)
        oname = [o[1] for o in OUTER if o[0] == d[3]][0]
        a('<div class="dim"><div class="dim-h"><div class="no">%d</div>'
          '<div><span class="nm">%s</span><span class="wt">　权重 %d%%　对外维度 %s</span></div>'
          '<div class="sc"><span class="tag t-%s">%s</span>'
          '<span class="num">%.1f <small>/ 5.0</small></span></div></div>'
          '<div class="dim-b">'
          '<div><div class="lb">行为解读（本档）</div><p>%s</p></div>'
          '<div><div class="lb">风险面（这一维最可能出问题的地方）</div><p>%s</p></div>'
          '<div><div class="lb">优势场景（对文旅岗位的具体意义）</div><p>%s</p></div>'
          '<div><div class="lb">风险场景</div><p>%s</p></div>'
          '<div class="full"><div class="lb">取证追问（面试现场可直接念）</div>'
          '<div class="quote">「%s」<span class="q">追问目的：把自述还原成可核验的事实与原话；'
          '回答停留在态度与评价时，用「具体哪一次、当时你怎么做的、后来对方什么反应」三连追问；'
          '回答里出现「一般、多数、大家都」时，追问最近一次具体案例。</span></div></div>'
          '<div class="full"><div class="lb">后续动作</div><p>%s <b>该维度结论：</b>%s</p></div>'
          '</div></div>' % (RANK[k], d[1], d[2], oname, bc, bn, sc, an["strength"], an["risk"],
                             an["scene_u"], an["scene_r"], d[8], an["action"], an["verdict"]))
    a('</div>')

    # 六 红线与判定
    a('<div class="sec"><div class="sec-h"><span class="no">六</span><h2>红线核查与综合判定</h2>'
      '<span class="note">结论只给行 / 不行</span></div>')
    a('<div class="twocol">')
    a('<div class="card"><p class="lead"><b>红线核查（诚信与责任）</b></p>'
      '<div style="margin-top:10px"><table><thead><tr><th style="width:200px">核查项</th>'
      '<th style="width:110px">结果</th><th>事实依据</th></tr></thead><tbody>'
      '<tr><td>履历与业绩数据真实性</td><td><span class="tag t-good">未触发</span></td><td>简历与背景调查一致，业绩数字可追溯</td></tr>'
      '<tr><td>隐瞒重大信息</td><td><span class="tag t-good">未触发</span></td><td>主动说明过往团队变动与绩效情况</td></tr>'
      '<tr><td>责任归属</td><td><span class="tag t-good">未触发</span></td><td>STAR 叙述中三次提到「我」承担责任，未推给他人</td></tr>'
      '<tr><td>承诺兑现</td><td><span class="tag t-good">未触发</span></td><td>举例均为已兑现承诺，无反复失信记录</td></tr>'
      '</tbody></table></div>'
      '<div class="callout" style="margin-top:12px">红线未触发。但<b>诚信属底线项，不因得分高而豁免</b>；'
      '后续背调若出现与本次自述不一致的重大差异，按「先核实再定论」处理，不直接推翻结论。</div></div>')
    a('<div class="card"><p class="lead"><b>综合判定</b></p>'
      '<div class="verdict" style="margin-top:12px">'
      '<div class="vd win"><h4>行（须带教）</h4><ul>'
      '<li>加权总分 <b>%.2f</b> ≥ 3.0</li><li>8 子维均 ≥ 2.0，无维度塌陷</li>'
      '<li>诚信与责任红线复核未触发</li><li>核心维度情绪稳定 4.2，岗位授权基础成立</li></ul>'
      '<div style="margin-top:10px;font-size:13.5px;color:var(--ink2);line-height:1.8">'
      '<b>结论：</b>建议录用，但入职后 90 天内以<b>冲突处理</b>为唯一重点带教项，'
      '指定直属上级每月一次复盘，第 90 天复评；期间不单独授权跨机构利益冲突议题。</div></div>'
      '<div class="vd cond"><h4>若本次数据变化</h4><ul>'
      '<li>加权 2.4–3.0 → 有条件行：试岗 90 天 + 带教清单</li>'
      '<li>存在子维落在 2.0–2.9 → 该维列入带教观察项</li>'
      '<li>加权 &lt; 2.4 → 不行</li></ul></div>'
      '<div class="vd lose"><h4>直接不行的情形</h4><ul>'
      '<li>红线经复核确认成立</li><li>任一子维 &lt; 2.0（塌陷）</li>'
      '<li>情绪稳定或冲突处理 &lt; 2.0</li>'
      '<li>评委一致度 ICC &lt; 0.70 且复测仍不达标</li></ul></div></div></div>')
    a('</div></div>')

    # 七 流程
    a('<div class="sec"><div class="sec-h"><span class="no">七</span><h2>实施流程与效度保障</h2>'
      '<span class="note">从知情同意到入职后复测</span></div>')
    a('<div class="flow">')
    for sn, st, d, w in FLOW:
        a('<div class="step"><div class="sn">%s</div><div class="st">%s</div><p>%s</p><div class="when">⏱ %s</div></div>' % (sn, st, d, w))
    a('</div>')
    a('<div class="twocol" style="margin-top:14px">')
    a('<div class="card"><p class="lead"><b>效度保障四个抓手</b></p>'
      '<ul style="margin:10px 0 0 18px;font-size:14px;line-height:1.95;color:var(--ink2)">'
      '<li><b>一题多证据：</b>每个维度至少由 2 类方法覆盖（题 + 面 / 面 + 观察），单来源不作为结论；</li>'
      '<li><b>先自评后行为：</b>自评先做可降低防御，后做 SJT 与行为面，只拿两者差值做待验证假设；</li>'
      '<li><b>CR-retest：</b>关键 SJT 先写方案再答闭合项，压制分数膨胀；</li>'
      '<li><b>回溯验证：</b>每季度用入职 90 天复评结果回测预测效度，效度不达标的维度降权或替换。</li></ul></div>')
    a('<div class="card"><p class="lead"><b>风险与合规提示（大陆落地必做）</b></p>'
      '<ul style="margin:10px 0 0 18px;font-size:14px;line-height:1.95;color:var(--ink2)">'
      '<li>测试结论<b>不得作为录用唯一依据</b>，须与面谈、背景调查、业务测试合并使用——'
      '把性格/心理测试当录用「硬指标」已被公开报道定性为涉嫌就业歧视（劳动法第 3 条平等就业权）；</li>'
      '<li><b>知情同意</b>：事先讲清目的、谁看结果、怎么用、留存期限，并明确拒绝参加不影响录用；</li>'
      '<li><b>敏感个人信息</b>：心理测评数据按敏感个人信息处理，分层存储、留存不超过 1 年、离职后按约定处理；</li>'
      '<li><b>禁用临床量表</b>：SCL-90、SAS、SDS 等临床量表不得用于招聘决策；'
      '采购外部测评服务时对照 GB/T 45253-2025《互联网心理服务 心理测评服务通用规范》；</li>'
      '<li><b>不输出人格标签</b>：表述一律写成行为（例：「冲突情境中倾向私下回避，公开场合沟通不足」），'
      '不写「情商低」「不够圆滑」。</li></ul></div>')
    a('</div></div>')

    # 附录一
    a('<div class="sec"><div class="sec-h"><span class="no">附录一</span><h2>SJT 情境判断题示例与计分</h2>'
      '<span class="note">题库节选 · 完整题库建议 60 题轮换</span></div>')
    for sid, dim, stem, opts, score, rule in SJT:
        a('<div class="card" style="margin-bottom:12px">'
          '<div style="display:flex;gap:12px;align-items:center;margin-bottom:8px">'
          '<span class="tag t-gold">%s</span><b>%s</b></div>'
          '<p style="font-size:14.5px;line-height:1.85;color:var(--ink)">%s</p>'
          '<div style="margin:10px 0 8px;display:grid;grid-template-columns:1fr 1fr;gap:6px 18px">' % (sid, dim, stem))
        for o in opts:
            a('<div style="font-size:13.8px;line-height:1.8;color:var(--ink2)">%s</div>' % o)
        a('</div>'
          '<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:10px">'
          '<div style="background:#F4EFE2;border-radius:10px;padding:10px 13px;font-size:13.5px;line-height:1.8">'
          '<b style="color:#8A6C2E">计分</b><br>%s</div>'
          '<div style="background:var(--red-bg);border-radius:10px;padding:10px 13px;font-size:13.5px;line-height:1.8;color:#7A2B24">'
          '<b>防伪装规则</b><br>%s</div></div></div>' % (score, rule))
    a('<div class="callout" style="margin-top:6px"><b>题目设计纪律：</b>每题只测一个维度；四个选项在社会赞许性上尽量拉平，'
      '避免一眼即错的低质量干扰项；关键题保留 1–2 个「合理但不可验证」的选项用于识别伪装；'
      '题库每轮抽题时保证同一维度题量均衡，避免某维度题多导致的分数膨胀；'
      '施测时按 CR-retest 流程，先写一句应对方案再答闭合选项。</div>')
    a('</div>')

    # 附录二
    a('<div class="sec"><div class="sec-h"><span class="no">附录二</span><h2>调研依据与一手来源</h2>'
      '<span class="note">简报：EQ测评调研简报_2026-10-24.md</span></div>')
    a('<div class="tw"><table><thead><tr><th style="width:70px">#</th><th>结论 / 依据</th>'
      '<th style="width:420px">来源</th></tr></thead><tbody>')
    for i, (t, u) in enumerate(SRC, 1):
        a('<tr><td>%d</td><td>%s</td><td class="srclist"><a href="%s">%s</a></td></tr>' % (i, t, u, u))
    a('</tbody></table></div>')
    a('<div class="callout" style="margin-top:12px"><b>取证提示：</b>若后续采购外部商业测评，'
      '须要求供应商提供常模样本、原始信效度数据与开发论文；'
      '「Barron EQ 4C」「40 题四分支版 EQ-i 2.0」「ASQ 题量与信效度」三项在本次检索中未见可核实公开来源，'
      '在拿到一手材料前不对外引用。</div>')
    a('</div>')

    # 收口
    a('<div class="sec"><div class="sec-h"><span class="no">收口</span><h2>交付物与下一步</h2>'
      '<span class="note">集团行政人事部 · 2026-10-24</span></div>')
    a('<div class="twocol">')
    a('<div class="card"><p class="lead"><b>本方案交付的三个东西</b></p>'
      '<ul style="margin:10px 0 0 18px;font-size:14.5px;line-height:2;color:var(--ink2)">'
      '<li><b>一套可执行的情商测试框架</b>：对外 4 维度 + 教练版 8 子维 + 1 红线、7 个环节、0–5 行为锚定尺、判定规则与效度控制；</li>'
      '<li><b>一套结果呈现格式</b>：蛛网图直观定位 + 逐维度行为解读 + 取证追问 + 后续动作；</li>'
      '<li><b>一份可直接上手的题本样例</b>：6 道 SJT 示例与计分、防伪装规则，可扩成 60 题题库。</li></ul></div>')
    a('<div class="card"><p class="lead"><b>下一步三件事（建议顺序）</b></p>'
      '<ul style="margin:10px 0 0 18px;font-size:14.5px;line-height:2;color:var(--ink2)">'
      '<li><b>定岗位权重表</b>：先落 3 类岗位（管理 / 专业 / 服务一线）的子维权重差异，其余用通用权重；</li>'
      '<li><b>建 60 题题库并试标</b>：选 2 名在职管理者做样例锚定，确保 ICC(2,k) ≥ 0.70；</li>'
      '<li><b>跑一次真实人选</b>：用实测分数替换示例数据，验证判定规则与带教建议的可执行性。</li></ul></div>')
    a('</div>')
    a('<div class="foot">'
      '报告出具部门：集团行政人事部　|　方案版本 V1.0　|　生成日期 2026-10-24<br>'
      '口径说明：0–5 分制、加权总分与单项下限、结论「行 / 不行」，与集团既有称职度评估口径一致；'
      '依据栏写事实与原话，不写形容词。<br>'
      '说明：本页的分数、评委一致度与判读文字为<b>示例数据</b>，用于确认呈现格式与判定规则；'
      '正式使用时以实测数据替换。测试结果不作为录用唯一依据，须与面谈及背景调查合并使用。')
    a('</div></div></body></html>')
    return "\n".join(h)

if __name__ == "__main__":
    html = build_html()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("written:", OUT, os.path.getsize(OUT), "bytes")
    print("weighted total:", overall, "-> pct", pct(overall))
    print("outer:", OUTER_SCORE)
    for k in ["self", "regu", "empa", "comm", "conf", "rela", "infl", "team"]:
        print(" ", k, S[k], band(S[k]))
