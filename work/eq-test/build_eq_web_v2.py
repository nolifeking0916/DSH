# -*- coding: utf-8 -*-
"""生成「情商在线测试」单文件网页（候选人版）与 HR 汇总台。

- 题库：bank/eq_bank.json（研发态，含答案与解析）
- 产出：客户端题库剥离答案/解析，并把「正确选项+分值」编码进 c 字段，
        避免打开网页源码直接看到答案；同时每个设备对计分题做选项乱序。
- 用法：python3 build_eq_web_v2.py
"""
import json, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(BASE, "web", "eq_test_template_v2.html")
HR_TPL = os.path.join(BASE, "web", "eq_hr_console_template.html")
BANK = os.path.join(BASE, "bank", "eq_bank.json")
OUT_CAND = os.path.expanduser("~/Downloads/情商在线测试_候选人版_20261024.html")
OUT_HR = os.path.expanduser("~/Downloads/情商在线测试_HR汇总台_20261024.html")


def fnv1a(s):
    h = 2166136261
    for ch in s.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h & 0x3FFFFFFF


def validate(b):
    errs = []
    sjt = b.get("sjt", [])
    if len(sjt) != 60:
        errs.append("sjt 数量应为 60，实际 %d" % len(sjt))
    scored = [q for q in sjt if not q.get("consistency") and q["id"].startswith("Q")]
    cons = [q for q in sjt if q.get("consistency")]
    if len(scored) != 48:
        errs.append("计分题应为 48，实际 %d" % len(scored))
    if len(cons) != 12:
        errs.append("一致性题应为 12，实际 %d" % len(cons))
    dims = b.get("dimensions", [])
    if len(dims) != 8:
        errs.append("维度应为 8，实际 %d" % len(dims))
    for d in dims:
        n = len([q for q in scored if q["dimension"] == d["key"]])
        if n != 6:
            errs.append("维度 %s 计分题应为 6，实际 %d" % (d["key"], n))
    for q in sjt:
        if set(q.get("options", {}).keys()) != {"A", "B", "C", "D"}:
            errs.append("%s 选项不是 A/B/C/D" % q.get("id"))
        if q.get("answer") not in q.get("options", {}):
            errs.append("%s 的 answer 不在选项中" % q.get("id"))
        if not q.get("stem"):
            errs.append("%s 缺题干" % q.get("id"))
        if not q.get("consistency"):
            if q.get("score") not in (0, 1, 2):
                errs.append("%s 的 score 非法" % q.get("id"))
        else:
            if q.get("score") not in (0, None):
                errs.append("%s 一致性题 score 应为 0" % q.get("id"))
    pairs = {}
    for q in cons:
        pairs.setdefault(q.get("pair"), []).append(q)
    for p, lst in pairs.items():
        if len(lst) != 2:
            errs.append("一致性对 %s 有 %d 题（应为 2）" % (p, len(lst)))
    si = b.get("self_items", [])
    if len(si) != 16:
        errs.append("自评题应为 16，实际 %d" % len(si))
    stems = [q["stem"] for q in sjt]
    if len(stems) != len(set(stems)):
        errs.append("存在重复题干")
    # 一致性题：A/B 属积极型、C/D 属消极型（前端判定用）
    for q in cons:
        if not re.match(r"^[ABCD]$", q.get("answer", "")):
            errs.append("%s answer 非法" % q["id"])
    return errs


def client_bank(b):
    """剥离答案、解析、faking 标记，并把答案编码进 c 字段。"""
    out = {
        "meta": {"version": b["meta"].get("version", "1.0"), "title": b["meta"].get("title", "")},
        "dimensions": b["dimensions"],
        "self_scale": b["self_scale"],
        "self_items": [{"id": x["id"], "text": x["text"], "dimension": x["dimension"], "reverse": x["reverse"]}
                       for x in b["self_items"]],
        "sjt": [],
    }
    for q in b["sjt"]:
        item = {"id": q["id"], "dimension": q["dimension"], "stem": q["stem"],
                "options": {k: q["options"][k] for k in ("A", "B", "C", "D")}}
        if q.get("consistency"):
            item["consistency"] = True
            item["pair"] = q["pair"]
            item["c"] = "0"           # 一致性题不计分
        else:
            key = fnv1a(q["id"] + "|" + q["dimension"] + "|4")
            def _idx(x):
                return ("ABCD".index(x) + 1) if x in ("A", "B", "C", "D") else 0
            value = ("ABCD".index(q["answer"])) + _idx(q.get("second")) * 4 + _idx(q.get("third")) * 16
            item["c"] = format(value ^ key, "x")
        out["sjt"].append(item)
    return out


def main():
    with open(BANK, encoding="utf-8") as f:
        bank = json.load(f)
    errs = validate(bank)
    if errs:
        print("题库校验未通过：")
        for e in errs:
            print("  -", e)
        sys.exit(1)

    cb = client_bank(bank)
    with open(TPL, encoding="utf-8") as f:
        tpl = f.read()
    n_scored = len([q for q in cb["sjt"] if not q.get("consistency")])
    n_cons = len([q for q in cb["sjt"] if q.get("consistency")])
    meta = "共 %d 题（%d 道情境判断 + %d 道一致性校验）" % (len(cb["sjt"]), n_scored, n_cons)
    tpl = tpl.replace("{{BANK_META}}", meta)
    payload = json.dumps(cb, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tpl = tpl.replace("%%BANK_JSON%%", payload)
    if "%%BANK_JSON%%" in tpl:
        print("题库占位符替换失败")
        sys.exit(1)
    with open(OUT_CAND, "w", encoding="utf-8") as f:
        f.write(tpl)
    with open(HR_TPL, encoding="utf-8") as f:
        hr = f.read()
    with open(OUT_HR, "w", encoding="utf-8") as f:
        f.write(hr)
    print("候选人版:", OUT_CAND, os.path.getsize(OUT_CAND), "bytes")
    print("HR 汇总台:", OUT_HR, os.path.getsize(OUT_HR), "bytes")
    print("题库校验通过：%s；答案与解析已从页面剥离并编码，计分题按设备乱序" % meta)


if __name__ == "__main__":
    main()
