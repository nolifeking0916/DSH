#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把《集团人力近期重点工作进度表》展开成 v2 长表行数据。

输入：/tmp/tasks.json（建表当时的原始 39 条）
输出：rows_v2.json
行规则（见 目标版式定案_20261024.md）：
    行 = 事项 × 分项 × 日期
    - 有进展的 (分项, 日期) → 一行，带当天进展内容
    - 只有计划没有进展的 (事项, 日期) → 一行，分项=主分项，进展内容留空
    - 同一 (事项, 日期) 的计划只出现一次：优先挂在当天的第一条进展行上
"""
import json, re, os, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "/tmp/tasks.json"
OUT = os.path.join(HERE, "rows_v2.json")
YEAR = 2026

MODULES = ["人力资源规划", "招聘与配置", "培训与开发", "绩效管理", "薪酬福利", "员工关系", "待定位"]
NATURES = ["人", "流程", "成本", "其他"]

# 「4 个制度、6 个细则」的具体名单
# 来源：make_wecom_smartsheet.py 的《制度（试行稿）征求意见收集表》DOCS 清单，数目与概要完全吻合（4 制度 + 6 细则）
POLICY = [
    ("部门设置标准细则（7-1）", "人力资源规划"),
    ("员工作休细则（7-31）", "员工关系"),
    ("招聘管理制度（9-0）", "招聘与配置"),
    ("绩效考核管理制度（11-0）", "绩效管理"),
    ("绩效考核细则（11-2）", "绩效管理"),
    ("薪酬管理制度（12-0）", "薪酬福利"),
    ("晋升管理制度（36-0）", "人力资源规划"),
    ("O序列员工晋升管理细则（36-1）", "人力资源规划"),
    ("P序列员工晋升管理细则（36-2）", "人力资源规划"),
    ("M序列员工晋升管理细则（36-3）", "人力资源规划"),
]
POLICY_SUMMARY = ("4 个制度 + 6 个细则（逐项归口已定位，待补逐项进展）："
                  "部门设置标准细则（7-1）→人力资源规划；员工作休细则（7-31）→员工关系；"
                  "招聘管理制度（9-0）→招聘与配置；绩效考核管理制度（11-0）、绩效考核细则（11-2）→绩效管理；"
                  "薪酬管理制度（12-0）→薪酬福利；晋升管理制度（36-0）、O/P/M 序列员工晋升管理细则（36-1/2/3）→人力资源规划")
POLICY_SUB = "主要人力制度（4 制度 6 细则）"

# 事项级归属：seq -> (一级维度, 二级维度)
OWN = {
    1: ("薪酬福利", "成本"), 2: ("绩效管理", "流程"), 3: ("薪酬福利", "成本"),
    4: ("薪酬福利", "成本"), 5: ("薪酬福利", "成本"), 6: ("待定位", "流程"),
    7: ("待定位", "流程"), 8: ("待定位", "流程"), 9: ("绩效管理", "流程"),
    10: ("待定位", "流程"), 11: ("待定位", "流程"), 12: ("绩效管理", "流程"),
    13: ("人力资源规划", "成本"), 14: ("人力资源规划", "人"), 15: ("员工关系", "人"),
    16: ("人力资源规划", "流程"), 17: ("薪酬福利", "流程"), 18: ("员工关系", "流程"),
    19: ("员工关系", "流程"), 20: ("员工关系", "人"), 21: ("人力资源规划", "流程"),
    22: ("人力资源规划", "流程"), 23: ("薪酬福利", "流程"), 24: ("薪酬福利", "流程"),
    25: ("招聘与配置", "人"), 26: ("培训与开发", "人"), 27: ("培训与开发", "人"),
    28: ("培训与开发", "人"), 29: ("培训与开发", "人"), 30: ("人力资源规划", "人"),
    31: ("人力资源规划", "人"), 32: ("人力资源规划", "人"), 33: ("招聘与配置", "流程"),
    34: ("招聘与配置", "人"), 35: ("招聘与配置", "人"), 36: ("培训与开发", "人"),
    37: ("人力资源规划", "人"), 38: ("人力资源规划", "流程"), 39: ("人力资源规划", "流程"),
}

# 分项展开：只展开「源文本点名了子项」的 4 条；其余分项 = 事项名
SPLIT = {
    1:  ["茅森提点", "恐龙提点", "聚力提点"],
    9:  ["研创院考核方案", "工程考核方案"],
    22: ["行政管理中心", "财务和创建", "其余机构"],
    23: ["集团本部", "创建部", "其余机构"],
}

# 进展逐分项归属（源文本点名到子项时，手工切分到子项粒度）
PROG = {
    1:  [("1010", "茅森提点", "已提报董事长，待确认"),
         ("1010", "恐龙提点", "已提报董事长，待确认"),
         ("1012", "聚力提点", "已提报董事长，待确认")],
    9:  [("1018", "研创院考核方案", "完成研创院考核方案初稿")],
    22: [("1018", "行政管理中心", "已完成复核"),
         ("1018", "财务和创建", "需核查"),
         ("1018", "其余机构", "待抽查")],
    23: [("1018", "集团本部", "已完成系统后台调整；待核查"),
         ("1018", "创建部", "待核查"),
         ("1018", "其余机构", "待抽查")],
}

DATE_TYPO = {"1118": "1018"}
NOTES = []   # 清洗/存疑记录


def md_to_date(mmdd):
    return datetime.date(YEAR, int(mmdd[:2]), int(mmdd[2:]))


def norm_mmdd(tok):
    """笔误归一：1118→1018；20xx→10xx（1021/1023/1025 写成 2021/2023/2025）"""
    tok = DATE_TYPO.get(tok, tok)
    if tok.startswith("20"):
        tok = "10" + tok[2:]
    return tok


def strip_marker(s):
    return re.sub(r"^\s*\d+\s*[、.）)]\s*", "", s)


def parse_progress(seq, text, subs, start_mmdd):
    """返回 [(mmdd, 分项, 进展内容)]"""
    out = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^(\d{4})", line)
        if m:
            mmdd = norm_mmdd(m.group(1))
            body = line[4:].strip()
        else:
            mmdd = start_mmdd
            body = line
            NOTES.append({"seq": seq, "kind": "进展无日期", "raw": line,
                          "处理": f"按开始时间 {start_mmdd} 落行，标待核"})
        sub = None
        for s in subs:
            if s in body:
                sub = s
                break
        if sub is None:
            sub = subs[0]
        # 冒号左段命中分项时，右段才是进展内容
        content = body
        for sep in ("：", ":"):
            if sep in body:
                left, right = body.split(sep, 1)
                if left.strip() in subs:
                    sub, content = left.strip(), right.strip()
                break
        out.append((mmdd, sub, content))
    return out


def parse_plan(seq, text, start_mmdd):
    """返回 {mmdd: 计划文本}"""
    out = collections.OrderedDict()
    for raw in text.split("\n"):
        line = strip_marker(raw.strip())
        if not line or line in ("/", "-", "—", "无"):
            continue
        m = re.match(r"^(\d{4})\s*[-—~至]\s*(\d{4})", line)
        if m:
            a = md_to_date(norm_mmdd(m.group(1)))
            b = md_to_date(norm_mmdd(m.group(2)))
            body = line[m.end():].strip()
            d = a
            while d <= b:
                out.setdefault(d.strftime("%m%d"), []).append(body)
                d += datetime.timedelta(days=1)
            continue
        m2 = re.match(r"^(\d{4})", line)
        if not m2:
            NOTES.append({"seq": seq, "kind": "计划无日期", "raw": line,
                          "处理": "按开始时间落行，标待核"})
            out.setdefault(start_mmdd, []).append(line)
            continue
        mmdd = norm_mmdd(m2.group(1))
        body = line[m2.end():].strip()
        out.setdefault(mmdd, []).append(body)
    return {k: "；".join(v) for k, v in out.items()}


def main():
    tasks = json.load(open(SRC, encoding="utf-8"))
    rows = []
    per_seq = collections.Counter()

    for t in tasks:
        seq = t["seq"]
        mod, nat = OWN[seq]
        item = t["item"]
        summary = t["summary"]
        subs = SPLIT.get(seq, [item])
        # 制度类：分项 = 「4 制度 6 细则」这一批（逐制度归口写进简介，不虚构成 10 个分项行）
        if seq in (6, 7, 8):
            subs = [POLICY_SUB]
            mod = "待定位"
        sub_mod = {s: mod for s in subs}
        sub_intro = {}
        if seq in (6, 7, 8):
            for s in subs:
                sub_intro[s] = POLICY_SUMMARY
        else:
            for s in subs:
                sub_intro[s] = summary

        start_mmdd = t["start"][5:7] + t["start"][8:10]
        end = t["end"]
        start = t["start"]

        # 进展
        if seq in PROG:
            prog = [(mmdd, sub, content) for mmdd, sub, content in PROG[seq]]
        else:
            prog = parse_progress(seq, t["progress"], subs, start_mmdd)
        # 计划
        plan = parse_plan(seq, t["week"], start_mmdd)

        by_date = collections.OrderedDict()
        for mmdd, sub, content in prog:
            by_date.setdefault(mmdd, []).append((sub, content))

        all_dates = sorted(set(list(by_date.keys()) + list(plan.keys())),
                           key=lambda d: md_to_date(d))
        if not all_dates:
            # 事项存在但进展与计划都为空（如 #24）：按开始时间落一行，内容留空待补
            all_dates = [start_mmdd]
            NOTES.append({"seq": seq, "kind": "进展与计划均无",
                          "raw": "(空)", "处理": f"按开始时间 {start_mmdd} 落一行，内容待补"})
        for mmdd in all_dates:
            prog_list = by_date.get(mmdd, [])
            pl = plan.get(mmdd, "")
            if prog_list:
                for i, (sub, content) in enumerate(prog_list):
                    rows.append({
                        "事项序号": seq,
                        "一级维度（六大模块）": sub_mod.get(sub, mod),
                        "二级维度（人/流程/成本）": nat,
                        "具体事项": item,
                        "分项": sub,
                        "分项内容简介": sub_intro.get(sub, summary),
                        "进展日期": f"{YEAR}-{mmdd[:2]}-{mmdd[2:]} 00:00:00",
                        "进展内容": content,
                        "开始时间": start,
                        "完成时间": end,
                        "当日计划（周计划）": pl if i == 0 else "",
                        "责任人": t["owner"],
                        "负责人": t["lead"],
                        "负责人类型": t["typ"],
                        "协调事项": t["coord"],
                    })
                    per_seq[seq] += 1
            else:
                rows.append({
                    "事项序号": seq,
                    "一级维度（六大模块）": sub_mod.get(subs[0], mod),
                    "二级维度（人/流程/成本）": nat,
                    "具体事项": item,
                    "分项": subs[0],
                    "分项内容简介": sub_intro.get(subs[0], summary),
                    "进展日期": f"{YEAR}-{mmdd[:2]}-{mmdd[2:]} 00:00:00",
                    "进展内容": "",
                    "开始时间": start,
                    "完成时间": end,
                    "当日计划（周计划）": pl,
                    "责任人": t["owner"],
                    "负责人": t["lead"],
                    "负责人类型": t["typ"],
                    "协调事项": t["coord"],
                })
                per_seq[seq] += 1

    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("总行数:", len(rows))
    print("按模块:", dict(collections.Counter(r["一级维度（六大模块）"] for r in rows)))
    print("按性质:", dict(collections.Counter(r["二级维度（人/流程/成本）"] for r in rows)))
    print("有进展行:", sum(1 for r in rows if r["进展内容"]))
    print("只有计划的行:", sum(1 for r in rows if not r["进展内容"] and r["当日计划（周计划）"]))
    print("空行(既无进展也无计划):", sum(1 for r in rows if not r["进展内容"] and not r["当日计划（周计划）"]))
    print("事项覆盖:", len(per_seq), "单事项行数区间:", min(per_seq.values()), "-", max(per_seq.values()))
    print("--- 清洗备注 ---")
    for n in NOTES:
        print(n)
    print("输出:", OUT)


if __name__ == "__main__":
    main()
