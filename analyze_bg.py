# -*- coding: utf-8 -*-
"""分析在职员工中具有景区/度假区/乐园/酒店工作背景的人"""
import json, re, sys, collections

SPILL = "/var/folders/gf/k4dsxpz511s5386jkv94mp_m0000gn/T/dsh-spill-jF7mlK/session-68fd6f4ba295/37cd35228569-mcp__hrq-pg__query_sql.txt"

RAW = json.load(open(SPILL, encoding="utf-8"))
rows = RAW["rows"]
cols = RAW["columns"]
data = [dict(zip(cols, r)) for r in rows]
print("rows:", len(data), "persons:", len({d["id"] for d in data}))

INTERNAL = re.compile(r"(云上草原|云上|茅山森林世界|茅森|松鼠|星空|景尚|大竹海|熊猫部落|恐龙酒店)")

RULES = [
    ("乐园/主题公园", re.compile(r"(乐园|主题公园|游乐园|水上乐园|欢乐谷|方特|迪士尼|环球影城|海洋公园|野生动物园|动物园|恐龙园|嬉戏谷|长隆|宋城|童世界|融创文旅城|融创乐园|世嘉|影视乐园|影视城|横店|水世界|海洋馆|欢乐世界|环球恐龙城|大马戏|千古情|万岁山|婺女洲|葛仙山|启封故园|尼山圣境|炭河)")),
    ("景区", re.compile(r"(景区|风景区|旅游区|索道|盐湖城|百草园|百草原|乌镇|水镇|拈花湾|孝道园|龙之梦|天目湖|千岛湖|古镇|古城|文化园|生态园|漂流|旅游发展|旅游开发|旅游投资|文化旅游|文旅|华侨城|瘦西湖|山景区)")),
    ("度假区", re.compile(r"(度假区|度假村|度假酒店|温泉|山庄|疗养|庄园|度假)")),
    ("酒店", re.compile(r"(酒店|宾馆|饭店|客栈|民宿|大酒店|酒店管理|酒店公寓|万豪|希尔顿|喜来登|洲际|凯悦|香格里拉|温德姆|华美达|维也纳|全季|如家|汉庭|亚朵|格林豪泰|锦江|开元|君澜|铂尔曼|诺富特|皇冠假日|智选假日|豪生|万丽|悦榕庄|凯莱|远洲|白天鹅|丽笙|建国饭店|维景|南苑|裸心|悦华|嘉华|福朋|凯宾斯基|丽晶)")),
]
ORDER = ["乐园/主题公园", "景区", "度假区", "酒店"]

def cats(c):
    c = (c or "").strip()
    return [name for name, rx in RULES if rx.search(c)]

# 诊断：命中公司名清单
hits = collections.Counter()
for d in data:
    for name in cats(d["prev_company"]):
        hits[(d["prev_company"], name)] += 1

# 未命中但像旅游相关的公司
suspect = collections.Counter()
for d in data:
    c = d["prev_company"] or ""
    if not cats(c) and re.search(r"(旅游|文旅|文化|园|山|湖|岛|镇|谷|城|温泉|庄|演艺|景区|索道)", c):
        suspect[c] += 1

print("\n=== 未命中但疑似相关的公司（前 60）===")
for c, n in suspect.most_common(60):
    print(n, c)

print("\n=== 各类别命中人数（按人）===")
per = collections.defaultdict(set)
for d in data:
    for name in cats(d["prev_company"]):
        per[name].add(d["id"])
for name in ORDER:
    print(name, len(per[name]))
print("任一类别:", len(set().union(*per.values())) if per else 0)
print("总在职行数对应人员:", len({d['id'] for d in data}))
