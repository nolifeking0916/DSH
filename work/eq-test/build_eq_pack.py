# -*- coding: utf-8 -*-
"""生成《情商测试_评委打分表与题本》xlsx（评委现场用）。
口径：0–5 分制、加权分 + 单项下限、结论「行 / 不行」，与集团既有称职度评估一致。
"""
import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = os.path.expanduser("~/Downloads/情商测试_评委打分表与题本_20261024.xlsx")

GREEN = "1E4634"; GOLD = "C9A55C"; CREAM = "F5F0E4"; PAPER = "FAF9F4"
RED = "C0453B"; SAND = "8A7448"
thin = Side(style="thin", color="D8DEDA")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

DIMS = [
    ("self", "自我觉察", "A 情绪自控", 9,
     "能主动复盘情绪触发点（说得出「我当时心里第一反应是什么」），并据此调整；自评与行为证据基本一致。",
     "知道自己情绪波动大的场景，但描述笼统（「我脾气不太好」），改进动作偶发、难持续。",
     "把外因归给环境与他人（「都是他们不理解」），追问三次仍停在「我没错」；自评与他评严重背离。",
     "STAR 叙述里「我 / 我们」的比例；是否出现情绪觉察类自述句。",
     "讲一次你被下属或客户否定建议的经历。当时你心里第一反应是什么？你怎么处理的？如果重来会怎么做？"),
    ("regu", "情绪稳定", "A 情绪自控", 15,
     "被当众质疑后仍能继续推进事务，事后不迁怒；高压节点仍按节奏交付。",
     "能控制当场情绪，但事后反复内耗，或在非正式场合抱怨。",
     "情绪外溢（摔话、甩脸色、事后报复性分配任务），或压力下直接放弃职责。",
     "压力面谈中的语速与停顿；是否出现「就是气不过」类归因。",
     "讲一次你在高压节点（大型活动开园、集中客诉、上级临时加码）处理失当或险些失当的经历，当时你怎么稳住的？"),
    ("empa", "同理心", "B 同理沟通", 12,
     "在对方说出诉求前就能调整做法；能为不同立场的人分别说出其合理诉求。",
     "能理解显性诉求，但对情绪与潜台词识别偏慢，需要对方明说才反应过来。",
     "把情绪化表达当噪音（「他在无理取闹」），忽略他人感受带来的直接成本。",
     "复述他人情绪是否准确；是否使用「他其实是担心……」句式。",
     "讲一次你察觉同事情绪异常并主动介入的经历。你是怎么判断出他不对劲的？"),
    ("comm", "倾听表达", "B 同理沟通", 10,
     "复述对方观点准确，能用对方的语言说清结论；对方表达完之后能自然续讲。",
     "能听完，但复述有偏差；表达偏「信息堆叠」，对方需要二次确认。",
     "抢话、以说代听；表达让对方明显不适或转入防御。",
     "复述偏差；是否出现信息堆叠、需对方二次确认。",
     "讲一次你因为没听懂对方真实诉求而返工的沟通。你后来是怎么补上这一课的？"),
    ("conf", "冲突处理", "C 冲突与协作", 15,
     "能在公开场合处理分歧而不伤关系，冲突后合作效率不下降。",
     "私下沟通能解决，但公开或跨部门场景倾向回避与拖延，私下解决后再把情绪带进流程。",
     "回避、背后议论、迁怒第三方，或用权压服。",
     "冲突是否公开处理；是否出现「私下我们…」式回避。",
     "讲一次你和同事或上级有明确利益冲突的经历。你怎么处理的？后来关系和工作各是什么结果？"),
    ("rela", "关系经营", "D 关系与影响", 15,
     "与上级、平级、下属都能建立稳定信任，在需要时借得到力。",
     "关系维持尚可，合作多靠流程与上级推动，主动经营不足。",
     "关系只用于办事，人情与立场绑定；被提醒后仍不调整。",
     "是否记住并回应对方过往关注点；跨机构合作的主动联络频次。",
     "讲一次你主动修复一段恶化的工作关系。你做了什么让对方愿意重新合作？"),
    ("infl", "影响力说服", "D 关系与影响", 13,
     "能用事实与他人利益说服人，在存在反对意见时仍能推动落地。",
     "靠职级与流程推动，说服效果一般；面对利益受损方时推动力下降。",
     "命令式或情绪化施压；推不动就绕道、抱怨或放弃。",
     "说服时是否引用对方关切；是否给反对者留台阶。",
     "讲一次你成功说服反对你的人支持方案的经历。你怎么找到他真正在意的点？"),
    ("team", "协作补位", "C 冲突与协作", 11,
     "主动补位且边界清晰；不抢功也不甩锅，团队协作成本低。",
     "配合度高但被动，等指派；补位时边界表达偏软，容易被默认为默认承接。",
     "边界模糊导致他人无法预期，或遇事推诿、抢功。",
     "补位时是否同步说清代价与归属；功劳表述方式。",
     "讲一次你主动接过不属于自己职责的事，或你明确拒绝了一次不合理要求。"),
]

DIMS = sorted(DIMS, key=lambda d: -d[3])   # 与 HTML 报告一致：按权重降序

OUTER = [
    ("A", "情绪自控", "自我觉察 + 情绪稳定", 25, "压力下不被情绪带走，能识别自己的触发点并调整行为"),
    ("B", "同理沟通", "同理心 + 倾听表达", 25, "读得懂对方情绪与潜台词，也让对方接得住自己的话"),
    ("C", "冲突与协作", "冲突处理 + 协作补位", 25, "分歧摆到台面上，协作时能补位也守得住边界"),
    ("D", "关系与影响", "关系经营 + 影响力说服", 25, "把人和事一起推得动，三条线关系都可用"),
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
     "B 或 C 计 2 分 / A 计 1 分 / D 计 0 分", "选 A 若伴随情绪施压，则本项不得高于 3 分"),
    ("S-22", "协作补位", "同一项目里同事临时请假，他手上有一项和你冲突的交付。你的处理：",
     ["A. 先接下，同时明确告诉他回来后怎么交接",
      "B. 直接接下，先不说，等他回来再说",
      "C. 找第三方判断该不该接",
      "D. 明确说自己手上的事更急，不接"],
     "A 计 2 分 / B 计 1 分 / C 计 0 分 / D 计 0 分", "选 B 记「边界模糊」；选 D 记「边界偏硬」，需追问是否有协商过程"),
]

HDR = PatternFill("solid", fgColor=GREEN)
SUB = PatternFill("solid", fgColor=CREAM)
TITLE_F = Font(size=15, bold=True, color=GREEN)
HDR_F = Font(size=10.5, bold=True, color="FFFFFF")
BODY_F = Font(size=10.5, color="1D2A23")
WRAP = Alignment(wrap_text=True, vertical="top")
WRAP_C = Alignment(wrap_text=True, vertical="center", horizontal="center")


def style_header(ws, row, ncol, fill=HDR, font=HDR_F, height=30):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = BORDER
    ws.row_dimensions[row].height = height


def set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def body_style(ws, r1, r2, ncol, fill_even=None):
    for r in range(r1, r2 + 1):
        for c in range(1, ncol + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = BORDER
            if cell.font is None or cell.font.size is None:
                cell.font = BODY_F
            if cell.alignment.vertical is None:
                cell.alignment = WRAP
            if fill_even and (r - r1) % 2 == 1:
                cell.fill = fill_even


wb = Workbook()

# ---------------- Sheet 0 使用说明 ----------------
ws = wb.active
ws.title = "使用说明"
set_widths(ws, [22, 96, 26])
rows = [
    ("方案", "候选人测试二 · 情商与关系管理测试（EQ Test）", "V1.0 / 2026-10-24"),
    ("出具部门", "集团行政人事部", "—"),
    ("测试定位", "在整体评估（专业技能 / 管理技能 / 发展潜力，各 33%）中作为独立测试存在，为管理技能与发展潜力提供关键证据；不新增维度、不改权重", "结论仍为「行 / 不行」"),
    ("评分口径", "0–5 分制；5 分可授权、3 分达标、1 分不达标、0 分无有效行为证据；加权总分 = Σ(维度均分×权重)；百分制 = 总分×20", "合格线 3.0 分 / 60 分"),
    ("判定规则", "行：加权 ≥ 3.0 且 8 子维均 ≥ 2.0 且红线复核未确认　|　有条件行：加权 2.4–3.0 或存在子维 2.0–2.9　|　不行：加权 < 2.4 或任一子维 < 2.0 或红线确认", "见「汇总与判定」页"),
    ("红线", "诚信与责任：捏造履历与业绩、隐瞒重大信息、推责给不在场或弱势一方、反复失信、不当得利。红线只触发复核，须写事实依据与原话，复核确认后才影响结论", "不参与加权"),
    ("评委配置", "4 名评委独立打分后合议；同一维度评分差异 > 1 分必须回原始证据复核；BARS 行为面一致率 ICC(2,k) ≥ 0.70（通行门槛 0.60，本方案加严）", "低于 0.70 先校准再施测"),
    ("施测顺序", "知情同意 → 自评（仅生成假设，不计分）→ SJT（CR-retest：先写方案再答闭合选项）→ 行为面 → 小组任务 → 压力情景收尾 → 汇判", "自评置前可降低防御"),
    ("依据纪律", "每条评分写事实与候选人原话，不写形容词；无证据的分数不计入合议；汇报只写行为（例：「冲突情境中倾向私下回避」），不写「情商低」", "沿用集团既有评分纪律"),
    ("合规要求", "结果不得作为录用唯一依据；心理测评数据按敏感个人信息处理，留存不超过 1 年；不使用 SCL-90 / SAS / SDS 等临床量表；采购外部测评对照 GB/T 45253-2025", "已知悉知情同意"),
    ("对外维度", "对外只报 4 个 EQ 维度（情绪自控 / 同理沟通 / 冲突与协作 / 关系与影响）；8 个子维只进教练版与蛛网图", "维度过多结论不可用"),
    ("配套材料", "《候选人测试二_情商测试_设计与结果呈现_20261024.html》（设计与呈现）与《EQ测评调研简报_2026-10-24.md》（模型与工具调研依据）", "同日交付"),
]
ws["A1"] = "情商测试 · 评委打分表与题本 使用说明"
ws["A1"].font = TITLE_F
ws.merge_cells("A1:C1")
ws.row_dimensions[1].height = 26
hdr = ["项目", "口径与做法", "备注"]
for i, h in enumerate(hdr, 1):
    ws.cell(row=2, column=i, value=h)
style_header(ws, 2, 3)
for i, (a, b, c) in enumerate(rows, 3):
    ws.cell(row=i, column=1, value=a).font = Font(size=10.5, bold=True, color=GREEN)
    ws.cell(row=i, column=2, value=b)
    ws.cell(row=i, column=3, value=c)
body_style(ws, 3, 2 + len(rows), 3, PatternFill("solid", fgColor="FCFBF8"))
for r in range(3, 3 + len(rows)):
    ws.row_dimensions[r].height = 46
ws.freeze_panes = "A3"

# ---------------- Sheet 1 评委打分表 ----------------
ws = wb.create_sheet("评委打分表")
cols = ["序", "子维度", "对外维度", "权重%", "5 分锚点（可授权）", "3 分锚点（合格）", "1 分锚点（不达标）",
        "观察信号", "取证追问（可直接念）", "评委A", "评委B", "评委C", "评委D", "均分", "最低分", "极差",
        "一致性复核", "事实依据与原话（必填）", "档位"]
for i, h in enumerate(cols, 1):
    ws.cell(row=1, column=i, value=h)
style_header(ws, 1, len(cols), height=34)
for i, (key, name, outer, wt, a5, a3, a1, sig, ask) in enumerate(DIMS, 1):
    r = i + 1
    ws.cell(row=r, column=1, value=i)
    ws.cell(row=r, column=2, value=name).font = Font(size=10.5, bold=True, color=GREEN)
    ws.cell(row=r, column=3, value=outer)
    ws.cell(row=r, column=4, value=wt)
    ws.cell(row=r, column=5, value=a5)
    ws.cell(row=r, column=6, value=a3)
    ws.cell(row=r, column=7, value=a1)
    ws.cell(row=r, column=8, value=sig)
    ws.cell(row=r, column=9, value=ask)
    for c in range(10, 14):
        ws.cell(row=r, column=c).alignment = WRAP_C
    ws.cell(row=r, column=14, value='=IF(COUNT(J{r}:M{r})=0,"",ROUND(AVERAGE(J{r}:M{r}),2))'.format(r=r))
    ws.cell(row=r, column=15, value='=IF(COUNT(J{r}:M{r})=0,"",MIN(J{r}:M{r}))'.format(r=r))
    ws.cell(row=r, column=16, value='=IF(COUNT(J{r}:M{r})=0,"",MAX(J{r}:M{r})-MIN(J{r}:M{r}))'.format(r=r))
    ws.cell(row=r, column=17, value='=IF(COUNT(J{r}:M{r})=0,"",IF(P{r}>1,"需复核（差值>1）","一致"))'.format(r=r))
    ws.cell(row=r, column=19, value='=IF(N{r}="","",IF(N{r}>=4,"优势区",IF(N{r}>=3.4,"稳健区",IF(N{r}>=3,"达标区",IF(N{r}>=2.4,"带教区",IF(N{r}>=2,"边缘区","风险区"))))))'.format(r=r))
    ws.row_dimensions[r].height = 92
body_style(ws, 2, 9, len(cols), PatternFill("solid", fgColor="FCFBF8"))
set_widths(ws, [4, 12, 14, 7, 40, 40, 40, 26, 34, 7, 7, 7, 7, 8, 8, 7, 15, 42, 10])
ws.freeze_panes = "C2"
ws.auto_filter.ref = "A1:S9"

# ---------------- Sheet 2 汇总与判定 ----------------
ws = wb.create_sheet("汇总与判定")
for i, h in enumerate(["序", "子维度", "权重%", "均分（引自打分表）", "贡献分（0–5 加权）", "百分制贡献",
                       "最低分检查", "档位", "是否列入带教观察项"], 1):
    ws.cell(row=1, column=i, value=h)
style_header(ws, 1, 9, height=30)
for i, (key, name, outer, wt, *_rest) in enumerate(DIMS, 1):
    r = i + 1
    src = i + 1  # 打分表同名行
    ws.cell(row=r, column=1, value=i)
    ws.cell(row=r, column=2, value=name).font = Font(size=10.5, bold=True, color=GREEN)
    ws.cell(row=r, column=3, value=wt)
    ws.cell(row=r, column=4, value="='评委打分表'!N{}".format(src))
    ws.cell(row=r, column=5, value='=IF(D{r}="","",ROUND(D{r}*C{r}/100,3))'.format(r=r))
    ws.cell(row=r, column=6, value='=IF(E{r}="","",ROUND(E{r}*20,1))'.format(r=r))
    ws.cell(row=r, column=7, value='=IF(D{r}="","",IF(D{r}<2,"塌陷（<2.0）","正常"))'.format(r=r))
    ws.cell(row=r, column=8, value="='评委打分表'!S{}".format(src))
    ws.cell(row=r, column=9, value='=IF(D{r}="","",IF(D{r}<3,"列入带教观察项","—"))'.format(r=r))
    ws.row_dimensions[r].height = 22
body_style(ws, 2, 9, 9, PatternFill("solid", fgColor="FCFBF8"))

r = 11
summary = [
    ("加权总分（0–5）", '=IF(COUNT(E2:E9)=0,"",ROUND(SUM(E2:E9),2))', "合格线 3.0"),
    ("加权总分（百分制）", '=IF(B13="","",ROUND(B13*20,1))', "合格线 60"),
    ("最低子维分", '=IF(COUNT(D2:D9)=0,"",MIN(D2:D9))', "低于 2.0 判「不行」"),
    ("核心维度检查（情绪稳定 / 冲突处理）", '=IF(COUNT(D2:D9)<8,"待评分",IF(OR(D3<2,D6<2),"核心维塌陷 → 不行","通过"))', "两维任一 < 2.0 直接淘汰"),
    ("红线复核结果（手工填：未触发 / 待复核 / 确认）", "", "确认成立直接判「不行」"),
    ("带教项数量（明细见本页第 9 列）", '=COUNTIF(I2:I9,"列入带教观察项")', "＞0 即须列入 90 天带教清单"),
]
ws.cell(row=r, column=1, value="汇总与判定")
ws.cell(row=r, column=1).font = TITLE_F
ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
r += 1
for i, h in enumerate(["项目", "结果", "口径", "", "", "", "", "", ""], 1):
    ws.cell(row=r, column=i, value=h if i <= 3 else None)
style_header(ws, r, 3)
for j, (name, formula, note) in enumerate(summary):
    rr = r + 1 + j
    ws.cell(row=rr, column=1, value=name).font = Font(size=10.5, bold=True, color=GREEN)
    ws.cell(row=rr, column=2, value=formula if formula else None)
    ws.cell(row=rr, column=3, value=note)
    ws.row_dimensions[rr].height = 24
body_style(ws, r + 1, r + len(summary), 3, PatternFill("solid", fgColor="FCFBF8"))

rr = r + len(summary) + 2
ws.cell(row=rr, column=1, value="最终结论")
ws.cell(row=rr, column=1).font = Font(size=12, bold=True, color=GREEN)
ws.cell(row=rr, column=2, value='=IF(B17="确认","不行",IF(OR(B13<2.4,B15<2),"不行",IF(AND(B13>=3,B15>=2),"行","有条件行")))')
ws.cell(row=rr, column=2).font = Font(size=12, bold=True, color=GREEN)
ws.cell(row=rr, column=3, value='=IF(B20="行","建议录用；若存在带教项，按带教项执行 90 天复评",IF(B20="有条件行","试岗 / 带教 90 天，第 90 天复评","不予录用"))')
ws.row_dimensions[rr].height = 26
set_widths(ws, [4, 14, 8, 16, 15, 12, 14, 10, 20])
ws.freeze_panes = "A2"

# ---------------- Sheet 3 对外 4 维度 ----------------
ws = wb.create_sheet("对外4维度")
for i, h in enumerate(["代号", "对外维度", "包含子维", "权重%", "均分", "百分制", "档位", "一句话判读"], 1):
    ws.cell(row=1, column=i, value=h)
style_header(ws, 1, 8, height=26)
_rowof = {d[1]: i + 2 for i, d in enumerate(DIMS)}   # 子维度 → 汇总页行号
rowsmap = {"A": [_rowof["情绪稳定"], _rowof["自我觉察"]],
           "B": [_rowof["同理心"], _rowof["倾听表达"]],
           "C": [_rowof["冲突处理"], _rowof["协作补位"]],
           "D": [_rowof["关系经营"], _rowof["影响力说服"]]}
for i, (code, name, subs, w, desc) in enumerate(OUTER, 1):
    r = i + 1
    rlist = rowsmap[code]
    ws.cell(row=r, column=1, value=code)
    ws.cell(row=r, column=2, value=name).font = Font(size=10.5, bold=True, color=GREEN)
    ws.cell(row=r, column=3, value=subs)
    ws.cell(row=r, column=4, value=w)
    refs = ",".join("汇总与判定!D{0}".format(x) for x in rlist)
    ws.cell(row=r, column=5, value='=IF(COUNT({refs})<2,"",ROUND(AVERAGE({refs}),2))'.format(refs=refs))
    ws.cell(row=r, column=6, value='=IF(E{r}="","",ROUND(E{r}*20,1))'.format(r=r))
    ws.cell(row=r, column=7, value='=IF(E{r}="","",IF(E{r}>=4,"优势区",IF(E{r}>=3.4,"稳健区",IF(E{r}>=3,"达标区",IF(E{r}>=2.4,"带教区",IF(E{r}>=2,"边缘区","风险区"))))))'.format(r=r))
    ws.cell(row=r, column=8, value=desc)
    ws.row_dimensions[r].height = 30
body_style(ws, 2, 5, 8, PatternFill("solid", fgColor="FCFBF8"))
ws.cell(row=7, column=1, value="说明")
ws.cell(row=7, column=1).font = Font(size=10.5, bold=True, color=GREEN)
ws.cell(row=7, column=2, value="对外只报这 4 个维度；8 个子维与蛛网图属教练版明细，仅用于带教与复盘。")
ws.merge_cells(start_row=7, start_column=2, end_row=7, end_column=8)
ws.row_dimensions[7].height = 24
set_widths(ws, [7, 16, 24, 8, 9, 9, 10, 46])
ws.freeze_panes = "A2"

# ---------------- Sheet 4 SJT 题本 ----------------
ws = wb.create_sheet("SJT题本")
for i, h in enumerate(["题号", "维度", "题干", "选项 A", "选项 B", "选项 C", "选项 D", "计分",
                       "防伪装规则", "考生第一步：写「我会怎么做」", "考生选择", "评委观察备注"], 1):
    ws.cell(row=1, column=i, value=h)
style_header(ws, 1, 12, height=34)
for i, (sid, dim, stem, opts, score, rule) in enumerate(SJT, 1):
    r = i + 1
    ws.cell(row=r, column=1, value=sid)
    ws.cell(row=r, column=2, value=dim).font = Font(size=10.5, bold=True, color=GREEN)
    ws.cell(row=r, column=3, value=stem)
    for k, o in enumerate(opts):
        ws.cell(row=r, column=4 + k, value=o)
    ws.cell(row=r, column=8, value=score)
    ws.cell(row=r, column=9, value=rule)
    ws.cell(row=r, column=10, value=None)
    ws.cell(row=r, column=11, value=None)
    ws.cell(row=r, column=12, value=None)
    ws.row_dimensions[r].height = 76
body_style(ws, 2, 7, 12, PatternFill("solid", fgColor="FCFBF8"))
r = 9
notes = [
    "施测流程（CR-retest）：先让候选人用一句话写下「我会怎么做」（第 J 列），再在 A–D 中选择最接近的一项（第 K 列）。研究显示该流程抑制分数膨胀的效果优于考前警告语。",
    "题目设计纪律：每题只测一个维度；四个选项在社会赞许性上尽量拉平，避免一眼即错的低质量干扰项；关键题保留 1–2 个「合理但不可验证」的选项用于识别伪装。",
    "轮换规则：完整题库建议 60 题，每轮施测按维度均衡抽取同一维度题量，避免某维度题多导致分数膨胀。",
    "防伪装三查：作答过快、同向全选最优选项、自评与行为证据互相矛盾。任一命中时该维度不得高于 3 分。",
]
for i, t in enumerate(notes):
    rr = r + i
    ws.cell(row=rr, column=1, value="规则 %d" % (i + 1)).font = Font(size=10.5, bold=True, color=GREEN)
    ws.cell(row=rr, column=2, value=t)
    ws.merge_cells(start_row=rr, start_column=2, end_row=rr, end_column=12)
    ws.row_dimensions[rr].height = 30
    for c in range(1, 13):
        ws.cell(row=rr, column=c).fill = SUB
        ws.cell(row=rr, column=c).border = BORDER
set_widths(ws, [7, 11, 40, 34, 34, 34, 34, 24, 30, 26, 12, 26])
ws.freeze_panes = "C2"

wb.save(OUT)
print("written:", OUT, os.path.getsize(OUT), "bytes")
