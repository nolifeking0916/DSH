# -*- coding: utf-8 -*-
"""生成「情商在线测试」单文件网页（候选人版）与 HR 汇总台。

- 题库：bank/eq_bank.json（研发态，含答案与解析）
- 产出：客户端题库剥离答案/解析，并把「正确选项+分值」编码进 c 字段，
        避免打开网页源码直接看到答案；同时每个设备对计分题做选项乱序。
- 编码：答案域位布局 fixed-20261024（见下方「编码：答案域位布局」注释），
        与 web/eq_test_template_v2.html 的 decodeItem 一一对应。
- 用法：python3 build_eq_web_v2.py
"""
import json, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(BASE, "web", "eq_test_template_v2.html")
HR_TPL = os.path.join(BASE, "web", "eq_hr_console_template.html")
BANK = os.path.join(BASE, "bank", "eq_bank.json")
OUT_CAND = os.path.expanduser("~/Downloads/情商在线测试_候选人版_20261024.html")
OUT_HR = os.path.expanduser("~/Downloads/情商在线测试_HR汇总台_20261024.html")
OUT_ENCODED = os.path.join(os.path.dirname(BASE), "assessment-kit", "data", "eq_bank_encoded.json")


def fnv1a(s):
    h = 2166136261
    for ch in s.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h & 0x3FFFFFFF


# ============================ 编码：答案域位布局（fixed-20261024） ============================
# 位布局（packed 值，低位在左；共 9 位，落在 1 字节 + 1 位内）：
#
#   bit 8      版本标记 SCHEME_FLAG，恒为 1（0x100）。
#              旧格式（20261024 之前）没有这一位 → 解码器据此识别旧数据并回退，
#              绝不会把旧数据误当新格式解出错误答案。
#   bit 7      third  存在位（1 = 有第二个 1 分选项）
#   bit 6      second 存在位（1 = 有 1 分选项）
#   bits 5-4   third  选项序号 0..3 → A/B/C/D
#   bits 3-2   second 选项序号 0..3 → A/B/C/D
#   bits 1-0   answer 正确项序号 0..3 → A/B/C/D
#
# 为什么换掉旧布局（旧布局：1-based 序号 1..4 塞进 2 位域，解码用 %4）：
#   序号 4（D）= 二进制 100 溢出 2 位域 → 还原成 0，既丢掉 D 选项，
#   又和相邻字段撞位（second=D 会把 third 顶成别的选项）。
#   旧布局下 48 道计分题里有 10 题（Q01/Q04/Q06/Q10/Q21/Q23/Q28/Q37/Q41/Q45）
#   的「1 分项」集合失真，Q01 这类题会把 1 分发给错误选项。
#
# 新布局每个字段用「2 位序号（0..3）+ 1 位存在」，任何选项（含 D）都不会溢出到邻域；
# 状态空间 4(answer) × 5(second：无/A/B/C/D) × 5(third：无/A/B/C/D) = 100 种 ⊂ 256，
# 编码 ↔ 解码一一对应、无碰撞、无溢出。一致性题不计分 → 出厂哨兵 c="0"。
#
LETTERS = "ABCD"
SCHEME_FLAG = 0x100
ANS_SHIFT, ANS_MASK = 0, 0x3
SEC_SHIFT, SEC_MASK = 2, 0x3
THI_SHIFT, THI_MASK = 4, 0x3
SEC_PRESENT_BIT = 6
THI_PRESENT_BIT = 7


def pack_answer(q):
    """把一道题的 answer / second / third 打进一个整数（位域见上方注释）。"""
    ans = LETTERS.index(q["answer"]) if q.get("answer") in LETTERS else -1
    if ans < 0:
        raise ValueError("%s 的 answer 非法：%r" % (q.get("id"), q.get("answer")))
    v = SCHEME_FLAG | (ans << ANS_SHIFT)
    if q.get("second"):
        if q["second"] not in LETTERS:
            raise ValueError("%s 的 second 非法：%r" % (q.get("id"), q.get("second")))
        v |= (LETTERS.index(q["second"]) << SEC_SHIFT) | (1 << SEC_PRESENT_BIT)
    if q.get("third"):
        if q["third"] not in LETTERS:
            raise ValueError("%s 的 third 非法：%r" % (q.get("id"), q.get("third")))
        v |= (LETTERS.index(q["third"]) << THI_SHIFT) | (1 << THI_PRESENT_BIT)
    return v


def unpack_answer(v):
    """位域解包 → (answer, second, third)；不是本方案（缺版本标记位）返回 None。"""
    if not (v & SCHEME_FLAG):
        return None
    ans = LETTERS[v & ANS_MASK]
    sec = LETTERS[(v >> SEC_SHIFT) & SEC_MASK] if (v & (1 << SEC_PRESENT_BIT)) else None
    thi = LETTERS[(v >> THI_SHIFT) & THI_MASK] if (v & (1 << THI_PRESENT_BIT)) else None
    return ans, sec, thi


def encode_item(q):
    """一道题的出厂编码串 c。一致性题不参与计分 → 哨兵 "0"。"""
    if q.get("consistency"):
        return "0"
    key = fnv1a(q["id"] + "|" + q["dimension"] + "|4")
    c = format(pack_answer(q) ^ key, "x")
    if c == "0":                       # 与一致性题哨兵撞车（理论概率 ~1e-9/题），宁可不发
        raise RuntimeError("%s 的编码串与一致性题哨兵撞车" % q.get("id"))
    return c


def decode_item(q):
    """decodeItem 的 Python 镜像（与 web/eq_test_template_v2.html 的 decodeItem 一一对应）。"""
    c = q.get("c")
    if c == "0":                      # 一致性题哨兵：不计分、无答案
        return {"ans": None, "second": None, "third": None}
    key = fnv1a(q["id"] + "|" + q["dimension"] + "|4")
    v = (int(c, 16) ^ key) & 0xFFFFFFFF
    got = unpack_answer(v)
    if got is not None:
        ans, sec, thi = got
        return {"ans": ans, "second": sec, "third": thi}
    # 旧格式回退（仅让旧页面白屏时不炸；新出厂数据不会走到这里）
    best = v % 4
    t = v // 4
    s1 = t % 4
    s2 = (t // 4) % 4
    return {"ans": LETTERS[best],
            "second": (LETTERS[s1 - 1] if s1 else None),
            "third": (LETTERS[s2 - 1] if s2 else None)}


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
    """剥离答案、解析、faking 标记，并把答案编码进 c 字段（位布局见上方注释）。"""
    out = {
        "meta": {"version": b["meta"].get("version", "1.0"),
                 "title": b["meta"].get("title", ""),
                 "encoding": "fixed-20261024"},
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
        item["c"] = encode_item(q)     # 一致性题 → 哨兵 "0"；计分题 → 位域编码串
        out["sjt"].append(item)
    return out


def write_encoded_bank(bank):
    """产出 work/assessment-kit/data/eq_bank_encoded.json（集成方数据源）。

    与 bank/eq_bank.json 同结构：
      - meta 增加 "encoding":"fixed-20261024"；
      - sjt[i].c = 修好的编码串（一致性题出厂哨兵 "0"）；
      - answer / second / third 原文字段保留（供回归比对与集成方直接计分）。
    """
    out = json.loads(json.dumps(bank, ensure_ascii=False))   # 深拷贝，保持字段顺序
    out.setdefault("meta", {})["encoding"] = "fixed-20261024"
    for q in out["sjt"]:
        q["c"] = encode_item(q)
    d = os.path.dirname(OUT_ENCODED)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(OUT_ENCODED, "w", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
    return OUT_ENCODED


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
    enc_path = write_encoded_bank(bank)
    print("候选人版:", OUT_CAND, os.path.getsize(OUT_CAND), "bytes")
    print("HR 汇总台:", OUT_HR, os.path.getsize(OUT_HR), "bytes")
    print("编码题库:", enc_path, os.path.getsize(enc_path), "bytes")
    print("题库校验通过：%s；答案与解析已从页面剥离并编码（fixed-20261024），计分题按设备乱序" % meta)


if __name__ == "__main__":
    main()
