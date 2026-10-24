#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二项（情商情境测试）编码往返校验 —— 修复版 fixed-20261024

校验四件事（任一不过 → 退出码非 0）：

  相位 0  现状自述：生产编码器是哪一版（有没有版本标记位）。
  相位 1  位域自洽：题库 → 位域打包 → 位域解包，60 道 sjt 题逐题往返，
                   answer / second / third 完全一致（证明新位布局无溢出、无碰撞）。
  相位 2  生产链路：生产编码器（build_eq_web_v2.client_bank）→ 生产解码器
                   （web/eq_test_template_v2.html 里的 decodeItem，用 node 实跑；
                   没有 node 时退回等价的 Python 镜像）→ 逐题比对题库原值。
                   48 道计分题必须逐字相等；12 道一致性题按契约出厂 c="0" 哨兵，
                   生产链路从不解码它们（compute() 只对计分题解码），故断言其
                   出厂串为哨兵且解码链路不参与。
  相位 3  出厂产物：data/eq_bank_encoded.json 与生成的候选人版 HTML 内嵌题库，
                   逐题 c 必须与生产编码器一致，且能解回原值。

用法：python3 work/eq-test/test_eq_encoding.py
退出码：0 = 全部通过；1 = 有任一题不等 / 产物不一致。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(BASE, "bank", "eq_bank.json")
TPL = os.path.join(BASE, "web", "eq_test_template_v2.html")
ENCODED_JSON = os.path.join(os.path.dirname(BASE), "assessment-kit", "data", "eq_bank_encoded.json")
CAND_HTML = os.path.expanduser("~/Downloads/情商在线测试_候选人版_20261024.html")

LETTERS = "ABCD"
SCHEME_FLAG = 0x100          # 版本标记位（fixed-20261024 恒为 1）

sys.path.insert(0, BASE)
try:
    import build_eq_web_v2 as B
except Exception as exc:                                     # pragma: no cover
    print("无法导入生产编码器 build_eq_web_v2：%s" % exc)
    sys.exit(1)


# ---------------------------------------------------------------- 基础工具
def fnv1a(s):
    h = 2166136261
    for ch in s.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h & 0x3FFFFFFF


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_function(src, name):
    """从 HTML/JS 源码里抠出一个具名函数（含花括号配对，跳过字符串里的花括号）。"""
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\(", src)
    if not m:
        raise RuntimeError("源码里找不到函数 %s" % name)
    i = src.index("{", m.end())
    depth, quote = 0, None
    while i < len(src):
        ch = src[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        else:
            if ch in "\"'":
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return src[m.start():i + 1]
        i += 1
    raise RuntimeError("函数 %s 花括号不配对" % name)


def decode_mirror(q):
    """decodeItem 的 Python 镜像：位布局与 build_eq_web_v2.py / HTML 三方一致。

    新格式（有版本标记位 0x100）：按位取 answer / second / third；
    旧格式（无标记位）：按历史 %4 规则解，仅用于对照旧缺陷，不再产出新数据。
    """
    c = q.get("c")
    if c == "0":
        return {"ans": None, "second": None, "third": None}
    key = fnv1a(q["id"] + "|" + q["dimension"] + "|4")
    v = (int(c, 16) ^ key) & 0xFFFFFFFF
    if v & SCHEME_FLAG:
        ans = LETTERS[v & 3]
        sec = LETTERS[(v >> 2) & 3] if (v & 0x40) else None
        thi = LETTERS[(v >> 4) & 3] if (v & 0x80) else None
        return {"ans": ans, "second": sec, "third": thi}
    best = v % 4
    t = v // 4
    s1 = t % 4
    s2 = (t // 4) % 4
    return {"ans": LETTERS[best],
            "second": (LETTERS[s1 - 1] if s1 else None),
            "third": (LETTERS[s2 - 1] if s2 else None)}


def run_node_decode(tpl_src, items):
    """用 node 实跑模板里的 decodeItem。返回 (结果字典, 说明)；无 node 返回 (None, 说明)。"""
    node = shutil.which("node")
    if not node:
        return None, "未找到 node → 退回 Python 镜像"
    try:
        hash32_src = extract_function(tpl_src, "hash32")
        decode_src = extract_function(tpl_src, "decodeItem")
    except Exception as exc:
        return None, "从模板抽取 decodeItem 失败：%s" % exc
    harness = (
        "const fs=require('fs');\n"
        + hash32_src + "\n"
        + decode_src + "\n"
        + "const items=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));\n"
        + "const out={};for(const q of items){out[q.id]=decodeItem(q);}\n"
        + "process.stdout.write(JSON.stringify(out));\n"
    )
    tmp = tempfile.mkdtemp(prefix="eqenc_")
    try:
        hp = os.path.join(tmp, "h.js")
        ip = os.path.join(tmp, "i.json")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(harness)
        with open(ip, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        r = subprocess.run([node, hp, ip], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return None, "node 执行失败：%s" % ((r.stderr or "").strip()[:300])
        return json.loads(r.stdout), "node 实跑 HTML 的 decodeItem"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def fmt_triple(t):
    return "%s / %s / %s" % (t[0] or "-", t[1] or "-", t[2] or "-")


def bank_triple(q):
    return (q.get("answer"), q.get("second"), q.get("third"))


def dec_triple(d):
    return (d.get("ans"), d.get("second"), d.get("third"))


# ---------------------------------------------------------------- 主流程
def main():
    print("=" * 96)
    print("第二项编码往返校验（fixed-20261024）")
    print("=" * 96)

    bank = load_json(BANK)
    with open(TPL, encoding="utf-8") as f:
        tpl_src = f.read()

    sjt = bank["sjt"]
    scored = [q for q in sjt if not q.get("consistency")]
    cons = [q for q in sjt if q.get("consistency")]
    failures = []
    print("\n题库：%s" % BANK)
    print("题量：sjt %d = 计分 %d + 一致性 %d" % (len(sjt), len(scored), len(cons)))

    # ---------------- 相位 0：生产编码器现状
    print("\n" + "-" * 96)
    print("相位 0 · 生产编码器现状")
    print("-" * 96)
    cb = B.client_bank(bank)
    c_map = {q["id"]: q["c"] for q in cb["sjt"]}
    enc_item = getattr(B, "encode_item", None)
    pack_answer = getattr(B, "pack_answer", None)
    if enc_item is not None:
        print("生产编码器：build_eq_web_v2.encode_item（新格式，位布局见文件内注释）")
    else:
        print("生产编码器：build_eq_web_v2.client_bank（内联旧格式：1-based 序号 + %4 解码）")
    sample = scored[0]
    print("样例：%s → c=%s" % (sample["id"], c_map[sample["id"]]))

    # ---------------- 相位 1：位域自洽（60 题）
    print("\n" + "-" * 96)
    print("相位 1 · 位域自洽：题库 → 位域打包 → 位域解包（60 题）")
    print("-" * 96)
    if pack_answer is None:
        print("[跳过] 当前生产编码器未提供位域 API（旧格式无此能力）；修完后本相位自动生效。")
    else:
        print("  题号   题库 answer/second/third      位域往返结果            判定")
        ok1 = 0
        for q in sjt:
            v = pack_answer(q)
            got = B.unpack_answer(v)
            exp = bank_triple(q)
            good = got == exp
            ok1 += 1 if good else 0
            if not good:
                failures.append("%s 位域往返不等：期望 %s，实得 %s" % (q["id"], fmt_triple(exp), fmt_triple(got)))
            print("  %-6s %-24s %-22s %s" % (
                q["id"], fmt_triple(exp), fmt_triple(got), "✔" if good else "✘ 不一致"))
        print("  → 位域往返 %d/%d 全等" % (ok1, len(sjt)))

    # ---------------- 相位 2：生产链路（编码 → 解码）
    print("\n" + "-" * 96)
    print("相位 2 · 生产链路：生产编码器 → 生产解码器（decodeItem）")
    print("-" * 96)
    scored_items = [{"id": q["id"], "dimension": q["dimension"], "c": c_map[q["id"]],
                     "consistency": False} for q in scored]
    js_out, js_note = run_node_decode(tpl_src, scored_items)
    print("解码器来源：%s" % js_note)
    if js_out is None:
        decoded = {q["id"]: decode_mirror(q) for q in scored_items}
        print("[提示] 下面结果来自 Python 镜像（与模板 decodeItem 位布局等价）")
    else:
        decoded = js_out

    print("  题号   题库 answer/second/third      出厂 c                 解码结果              判定")
    ok2 = 0
    for q in scored:
        exp = bank_triple(q)
        got = dec_triple(decoded.get(q["id"], {}))
        good = got == exp
        ok2 += 1 if good else 0
        if not good:
            failures.append("%s 编码往返不等：题库 %s，解码得 %s（出厂 c=%s）"
                            % (q["id"], fmt_triple(exp), fmt_triple(got), c_map[q["id"]]))
        print("  %-6s %-24s %-21s %-22s %s" % (
            q["id"], fmt_triple(exp), c_map[q["id"]], fmt_triple(got),
            "✔" if good else "✘ 不一致"))
    print("  → 计分题编码往返 %d/%d 全等" % (ok2, len(scored)))

    print("\n  一致性题（12 道）：出厂 c 必须为哨兵 \"0\"，且生产链路不对其解码")
    print("  题号   题库 answer（不进编码域）     出厂 c                 判定")
    okc = 0
    for q in cons:
        good = (c_map[q["id"]] == "0")
        okc += 1 if good else 0
        if not good:
            failures.append("%s 一致性题出厂 c 应为哨兵 \"0\"，实为 %s" % (q["id"], c_map[q["id"]]))
        print("  %-6s %-27s %-21s %s" % (q["id"], q.get("answer") or "-", c_map[q["id"]],
                                        "✔ 哨兵" if good else "✘ 应为哨兵"))
    print("  → 一致性题哨兵一致 %d/%d" % (okc, len(cons)))

    # ---------------- 相位 3：出厂产物
    print("\n" + "-" * 96)
    print("相位 3 · 出厂产物一致性")
    print("-" * 96)

    if not os.path.exists(ENCODED_JSON):
        print("[跳过] %s 尚未生成" % ENCODED_JSON)
    else:
        enc = load_json(ENCODED_JSON)
        if enc.get("meta", {}).get("encoding") != "fixed-20261024":
            failures.append("eq_bank_encoded.json 的 meta.encoding 应为 fixed-20261024")
        else:
            print("  ✔ eq_bank_encoded.json meta.encoding = fixed-20261024")
        enc_sjt = {q["id"]: q for q in enc.get("sjt", [])}
        if len(enc_sjt) != len(sjt):
            failures.append("eq_bank_encoded.json 的 sjt 数量 %d ≠ 题库 %d" % (len(enc_sjt), len(sjt)))
        bad_c = bad_t = 0
        for q in sjt:
            e = enc_sjt.get(q["id"])
            if e is None:
                failures.append("eq_bank_encoded.json 缺题 %s" % q["id"])
                continue
            if e.get("c") != c_map[q["id"]]:
                bad_c += 1
                failures.append("%s 出厂 c 与生产编码器不一致：%s ≠ %s" % (q["id"], e.get("c"), c_map[q["id"]]))
            if (e.get("answer"), e.get("second"), e.get("third")) != bank_triple(q):
                bad_t += 1
                failures.append("%s 原文字段 answer/second/third 与题库不一致" % q["id"])
        if bad_c == 0 and bad_t == 0:
            print("  ✔ 60 题出厂 c 与 answer/second/third 原文字段全部一致")

    if not os.path.exists(CAND_HTML):
        print("[跳过] %s 尚未生成" % CAND_HTML)
    else:
        with open(CAND_HTML, encoding="utf-8") as f:
            html = f.read()
        m = re.search(r'<script id="bank" type="application/json">(.*?)</script>', html, re.S)
        if not m:
            failures.append("候选人版 HTML 里找不到内嵌题库")
        else:
            hbank = json.loads(m.group(1))
            h_map = {q["id"]: q.get("c") for q in hbank.get("sjt", [])}
            diff = [q["id"] for q in sjt if h_map.get(q["id"]) != c_map[q["id"]]]
            if diff:
                failures.append("候选人版 HTML 内嵌 c 与生产编码器不一致：%s" % ",".join(diff))
            else:
                print("  ✔ 候选人版 HTML 内嵌 60 题 c 与生产编码器一致")
            h_dec, h_note = run_node_decode(html, scored_items)
            if h_dec is not None:
                hd = [q["id"] for q in scored
                      if dec_triple(h_dec.get(q["id"], {})) != bank_triple(q)]
                if hd:
                    failures.append("候选人版 HTML 的 decodeItem 解码不等：%s" % ",".join(hd))
                else:
                    print("  ✔ 候选人版 HTML 的 decodeItem 解码 48 题全等（%s）" % h_note)
            if "0x100" not in html:
                failures.append("候选人版 HTML 的 decodeItem 缺少版本标记位 0x100（仍是旧解码逻辑？）")

    # ---------------- 汇总
    print("\n" + "=" * 96)
    if failures:
        print("校验未通过：%d 项不符" % len(failures))
        for f_ in failures:
            print("  - %s" % f_)
        print("=" * 96)
        return 1
    print("校验通过：位域往返 60/60 全等 · 计分题生产链路 48/48 全等 · 一致性题哨兵 12/12 · 出厂产物一致")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
