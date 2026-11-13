#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核心人才三联测试 · 衍生产物「重建一致」断言（票 #79）

三条腿都要绿才算过（2026-10-26 加固）
------------------------------------
  ① 真源核对   spec ↔ pilot/out/结果JSON_*.json
     门禁**自己**做这件事，不依赖生成器的 --cross-check（生成器是生成器，不是门）。
     结果 JSON 缺失 ⇒ 判红，不许「跳过即通过」：
     pilot/out/ 是 gitignore 的，新克隆/CI 上本来就没有，
     跳过就等于门禁在新环境里永远绿 —— 那等于没有门。
  ② 工作区一致 重建结果 ↔ reports/ 下当前文件
  ③ 已提交一致 重建结果 ↔ git HEAD:reports/ 下同一路径
     ② 和 ③ 分开，是为了抓住「产物被人手改了但没提交」：
     只比 ② 的话，把产物改了、再把 spec 改成能复刻它，门禁照样绿。

内容判据（三样都要相同）
------------------------
  ① 文本序列：去掉 <style>/<script> 与全部标签，实体反转义、空白折叠后按词元比。
     → 抓住所有「字」层面的漂移：分数、百分比、档位名、人名、判读文字、顺序。
  ② 版面骨架：只保留标签序列（标签名 + 排序后的属性，含 class 与内联 style 里的颜色），
     文本节点只留「这里有一段文字」的存在标记、不留内容。
     → 抓住「版面」层面的漂移：列顺序换了、某段被删了、内联配色改了。
  ③ 样式块：<style> 块单独抽出来，空白折叠后逐块比。
     → 抓住 <style> 里 CSS 的漂移（配色、间距、字号）。
     （2026-10-26 补：以前 <style> 被整块剥掉，改个背景色门禁也看不出来，
       与本文件原先宣称的「能抓配色漂移」不符。现在样式块是内容判据的一部分，
       空白仍按折叠后比，所以不会像字节判据那样把缩进噪声算成不一致。）

字节一致（sha256）另作一项单独报告：它是比内容判据更强的信号，
但不该当门禁 —— 理由同上（空白噪声）。

用法：
    python3 src/verify_report_artifacts.py                 # 默认内容判据
    python3 src/verify_report_artifacts.py --mode byte     # 要求逐字节相同
    python3 src/verify_report_artifacts.py --mode both     # 两者都要
    python3 src/verify_report_artifacts.py --keep          # 保留临时目录便于人工看
    python3 src/verify_report_artifacts.py --png           # 一并比对 PNG（Chrome 版本敏感）

退出码：
    0 = 三条腿都绿
    1 = 有内容不一致（并打印差异）
    2 = 跑不起来（结果 JSON 缺失、产物缺失、git 取不到、no_source 清单不完整等）

注意：
    · 参照 B（git HEAD）要求 --reports 指向**仓内**已提交的目录（默认 reports/）。
      若指向仓外路径，git show 取不到该路径，门禁判红（exit 2）——这是有意的：
      「已提交产物」这条腿只有在仓内参照物存在时才有意义。
    · 结果 JSON（pilot/out/）被 gitignore，新克隆/CI 上必然缺失 ⇒ 门禁必然红。
      这是刻意的：要真源核对，就得有真源；拿不到真源就不许说「一致」。
      跑门禁前请先按 pilot/ 流程生成结果 JSON。

本脚本**只读** reports/ 下的产物、**只读** git HEAD：重建结果一律写进临时目录，
绝不覆盖已提交产物，也绝不写仓内任何东西。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILDER = os.path.join(HERE, "build_comparison_artifacts.py")
DEFAULT_REPORTS = os.path.join(ROOT, "reports")
DEFAULT_SPEC = os.path.join(HERE, "comparison_spec.json")

F_COVER = "核心人才三联测试_汇总封面_%s.html"
F_TABLE = "三人核心人才三联测试_对比总表_%s.html"
F_LONG = "三人核心人才三联测试_苹果风长图_%s.html"

TAG_RE = re.compile(r"<[^>]+>")
STYLE_RE = re.compile(r"<style.*?</style>", re.S)
SCRIPT_RE = re.compile(r"<script.*?</script>", re.S)
ATTR_RE = re.compile(r"""([a-zA-Z_:][-\w:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")
WS_RE = re.compile(r"\s+")
PATH_TOKEN_RE = re.compile(r"[^.\[\]]+|\[\d+\]")

# no_source 清单必须覆盖到的字段（每个受测人都得有）
NO_SOURCE_REQUIRED = ("profile.edu_tier", "profile.org", "profile.hr_level")


# ── 基础工具 ──────────────────────────────────────────────────────────────────
def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def strip_blocks(html):
    return STYLE_RE.sub("", SCRIPT_RE.sub("", html))


def text_tokens(html):
    """归一化①：可读文本词元序列（去掉标签、样式、脚本，实体反转义，空白折叠）。"""
    import html as htmlmod
    s = strip_blocks(html)
    s = TAG_RE.sub(" ", s)
    s = htmlmod.unescape(s)
    return s.split()


def markup_skeleton(html):
    """归一化②：版面骨架（标签名 + 排序后的属性），文本节点只留存在标记。"""
    s = strip_blocks(html)
    out = []
    pos = 0
    for m in TAG_RE.finditer(s):
        if s[pos:m.start()].strip():
            out.append(("#text",))
        out.append(normalize_tag(m.group(0)))
        pos = m.end()
    if s[pos:].strip():
        out.append(("#text",))
    return out


def normalize_tag(tag):
    s = tag.strip()
    if s.startswith("</"):
        return ("close", s[2:-1].strip().lower())
    if s.startswith("<!") or s.startswith("<?"):
        return ("decl", s.lower())
    inner = s[1:].strip()
    name = re.split(r"[\s/>]", inner, 1)[0].lower()
    attrs = {}
    for m in ATTR_RE.finditer(inner):
        val = m.group(2)
        if val is None:
            val = m.group(3)
        if val is None:
            val = m.group(4)
        attrs[m.group(1).lower()] = val
    return ("tag", name, tuple(sorted(attrs.items())))


def style_blocks(html):
    """归一化③：<style> 块的内容（去标签、空白折叠）——样式漂移要比，不能整块剥掉。"""
    out = []
    for m in STYLE_RE.finditer(html):
        css = re.sub(r"</?style[^>]*>", "", m.group(0), flags=re.I)
        out.append(WS_RE.sub(" ", css).strip())
    return out


def first_diff(a, b, label, limit=12):
    """给出第一处不同及其上下文（人类可读）。"""
    out = []
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        out.append("  %s：%s" % (label, tag))
        for x in list(a[i1:i2])[:limit]:
            out.append("    - %s" % (x,))
        for x in list(b[j1:j2])[:limit]:
            out.append("    + %s" % (x,))
        break
    return out


def first_char_diff(a, b, label, width=60):
    """长字符串（CSS）的第一处不同：给字符偏移与一段窗口，别整块刷屏。"""
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    out = ["  %s：第 %d 个字符起不同" % (label, i)]
    out.append("    - …%s…" % a[max(0, i - 25):i + width])
    out.append("    + …%s…" % b[max(0, i - 25):i + width])
    return out


# ── git：取 HEAD 里的产物 ────────────────────────────────────────────────────
def git_repo_root():
    """定位 git 仓根。git show 必须从仓根下按仓内相对路径取文件。"""
    try:
        p = subprocess.run(["git", "-C", ROOT, "rev-parse", "--show-toplevel"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        return None, "git 不可用：%s" % e
    if p.returncode != 0:
        return None, p.stderr.decode("utf-8", "replace").strip() or "git rev-parse 失败"
    root = p.stdout.decode("utf-8", "replace").strip()
    return (root or None), (None if root else "git rev-parse 输出为空")


def git_head_bytes(repo_root, rel_path):
    """取 HEAD:<rel_path> 的字节；失败返回 (None, 错误说明)。"""
    try:
        p = subprocess.run(["git", "-C", repo_root, "show", "HEAD:" + rel_path],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        return None, "git 不可用：%s" % e
    if p.returncode != 0:
        return None, p.stderr.decode("utf-8", "replace").strip() or "git show 失败"
    return p.stdout, None


# ── ① 真源核对（门禁自己做）──────────────────────────────────────────────────
def gate_cross_check(spec_path, spec_raw):
    """spec ↔ pilot/out/结果JSON_*.json 的核对。

    返回 (status, 说明行列表)，status ∈ {"ok", "missing", "mismatch"}。

    口径（2026-10-26 定）：结果 JSON 缺失 ⇒ **missing（红）**，不许跳过当通过。
    生成器 build_comparison_artifacts.py 的 --cross-check 仍保留「跳过返回 0」的
    宽松行为——它是生成器不是门——但门不依赖它。
    """
    try:
        sys.path.insert(0, HERE)
        import build_comparison_artifacts as BCA
    except Exception as e:
        return "missing", ["失败：生成脚本导不进来，无法核对 spec 真源：%s" % e]

    try:
        spec = BCA.load_spec(spec_path)
    except Exception as e:
        return "missing", ["失败：spec 装载不了（生成脚本口径）：%s" % e]

    missing = []
    for p in spec_raw.get("people", []):
        rel = p.get("result_json", "")
        if not rel:
            missing.append("%s：spec 里没写 result_json" % p.get("name", "?"))
            continue
        if not os.path.exists(os.path.join(BCA.ROOT, rel)):
            missing.append(rel)
    if missing:
        lines = ["缺少 pilot/out/结果JSON_*.json，无法核对 spec 真源："]
        for m in missing:
            lines.append("  · %s" % m)
        lines.append("  → 结果 JSON 由 pilot/ 流程生成，且 pilot/out/ 整个被 gitignore")
        lines.append("    （pilot/out/.gitignore = *）。新克隆/CI 上取不到是正常状态，")
        lines.append("    但那意味着 spec 无从校验 —— 此时必须判红，不能「跳过即通过」。")
        return "missing", lines

    checked, problems = BCA.cross_check(spec)
    if problems:
        lines = ["真源核对：%d 份结果 JSON，发现 %d 处不一致" % (checked, len(problems))]
        for x in problems:
            lines.append("  · " + x)
        return "mismatch", lines
    return "ok", ["真源核对：%d 份结果 JSON，spec 与原始分/基础信息全部一致" % checked]


# ── ④ no_source 清单自检 ─────────────────────────────────────────────────────
def resolve_path(obj, path):
    """按 people[0].profile.edu_tier 这种写法取值；取不到返回 None。"""
    cur = obj
    for tok in PATH_TOKEN_RE.findall(path or ""):
        if tok.startswith("["):
            try:
                idx = int(tok[1:-1])
            except ValueError:
                return None
            if not isinstance(cur, list) or idx >= len(cur):
                return None
            cur = cur[idx]
        else:
            if not isinstance(cur, dict) or tok not in cur:
                return None
            cur = cur[tok]
    return cur


def check_no_source(spec):
    """spec 的 no_source 清单自检：路径可解析、钉住的值没漂移、必需项没漏。

    返回 (ok, 说明行列表)。清单的作用是「无来源的手抄值不再靠人记」，
    所以清单本身坏了也必须红，否则它很快变成摆设。
    """
    lines = []
    errors = []
    entries = spec.get("no_source")
    if not entries:
        return False, ["spec 缺少 \"no_source\" 清单："
                       "无来源的手抄值（prose 评语 / edu_tier / org / hr_level）必须显式列出（票 #79）"]
    for e in entries:
        path = e.get("path")
        if not path:
            errors.append("no_source 条目缺 path")
            continue
        val = resolve_path(spec, path)
        if val is None:
            errors.append("no_source 条目路径解析不到：%s" % path)
            continue
        if "value" in e and e["value"] != val:
            errors.append("no_source 条目的值已漂移：%s（清单记 %r，现值 %r）"
                          % (path, e["value"], val))
        for k in ("why_no_source", "human_basis"):
            if not (e.get(k) or "").strip():
                errors.append("no_source 条目 %s 缺 %s" % (path, k))
    paths = [e.get("path", "") for e in entries]
    for i in range(len(spec.get("people") or [])):
        for suffix in NO_SOURCE_REQUIRED:
            pfx = "people[%d].%s" % (i, suffix)
            if not any(p == pfx or p.startswith(pfx + ".") for p in paths):
                errors.append("no_source 漏了 %s" % pfx)
        if not any(p.startswith("people[%d].prose" % i) for p in paths):
            errors.append("no_source 漏了 people[%d].prose" % i)
    if errors:
        return False, ["no_source 清单自检未过："] + ["  · " + e for e in errors]
    return True, ["no_source 清单：%d 条，无来源的手抄值已显式登记（路径可解析、值未漂移）" % len(entries)]


# ── 比对 ─────────────────────────────────────────────────────────────────────
def compare_pair(name, ref_bytes, new_bytes, label):
    """把参照与重建结果比一遍。

    返回 dict：ok_text / ok_markup / ok_style / ok_byte / notes。
    内容判据 = ok_text and ok_markup and ok_style。
    """
    ref = ref_bytes.decode("utf-8")
    new = new_bytes.decode("utf-8")
    rt, nt = text_tokens(ref), text_tokens(new)
    rm, nm = markup_skeleton(ref), markup_skeleton(new)
    rs, ns = style_blocks(ref), style_blocks(new)
    notes = []
    ok_text = rt == nt
    ok_markup = rm == nm
    ok_style = rs == ns
    ok_byte = ref_bytes == new_bytes
    if not ok_text:
        notes += first_diff(rt, nt, "文本序列")
    if not ok_markup:
        notes += first_diff(rm, nm, "版面骨架")
    if ok_style:
        notes.append("样式块：%d 块，sha256 %s（相同）"
                     % (len(rs), sha256_bytes("\n".join(rs).encode("utf-8"))[:12]))
    else:
        notes.append("样式块：不同（参照 %d 块 / 重建 %d 块）" % (len(rs), len(ns)))
        for i in range(max(len(rs), len(ns))):
            a = rs[i] if i < len(rs) else ""
            b = ns[i] if i < len(ns) else ""
            if a != b:
                notes += first_char_diff(a, b, "样式块 #%d" % (i + 1))
                break
    if ok_text and ok_markup and ok_style:
        notes.append("内容判据：文本序列 %d 词元 + 版面骨架 %d 节点 + 样式块 %d 块，逐项相同"
                     % (len(rt), len(rm), len(rs)))
    else:
        notes.append("内容判据：不一致（文本序列 %s / 版面骨架 %s / 样式块 %s）"
                     % ("同" if ok_text else "异", "同" if ok_markup else "异",
                        "同" if ok_style else "异"))
    notes.append("字节判据：%s（参照 sha256 %s / 重建 sha256 %s）"
                 % ("逐字节相同" if ok_byte else "不同",
                    sha256_bytes(ref_bytes)[:12], sha256_bytes(new_bytes)[:12]))
    return {"ok_text": ok_text, "ok_markup": ok_markup, "ok_style": ok_style,
            "ok_byte": ok_byte, "notes": notes, "label": label}


# ── 入口 ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="三份衍生产物的「重建一致」断言（三方比对）")
    ap.add_argument("--reports", default=DEFAULT_REPORTS, help="已提交产物所在目录（只读）")
    ap.add_argument("--spec", default=DEFAULT_SPEC, help="生成脚本用的 spec")
    ap.add_argument("--mode", choices=["content", "byte", "both"], default="content",
                    help="门禁判据：content=文本+骨架+样式块；byte=逐字节；both=两者都要")
    ap.add_argument("--png", action="store_true", help="一并重建并比对三张 PNG 截图（Chrome 版本变了字节会变，默认不参与门禁）")
    ap.add_argument("--keep", action="store_true", help="保留临时目录")
    ap.add_argument("--quiet", action="store_true", help="只打印结论")
    args = ap.parse_args()

    # ── 读 spec ──────────────────────────────────────────────────────────────
    try:
        with open(args.spec, encoding="utf-8") as f:
            raw_spec = json.load(f)
    except Exception as e:
        print("失败：spec 读不了：%s" % e)
        return 2
    stamp = (raw_spec.get("meta", {}).get("date") or "").replace("-", "") or "00000000"
    names = [F_COVER % stamp, F_TABLE % stamp, F_LONG % stamp]

    # ── ① 真源核对（门禁自己做；缺 JSON 即红）────────────────────────────────
    src_status, src_lines = gate_cross_check(args.spec, raw_spec)
    if src_status != "ok":
        for line in src_lines:
            print(line)
        print()
        if src_status == "mismatch":
            print("结论：spec 与真源不一致（exit 1）")
            return 1
        print("结论：无法核对 spec 真源（exit 2）")
        return 2

    # ── ④ no_source 清单自检 ─────────────────────────────────────────────────
    ns_ok, ns_lines = check_no_source(raw_spec)
    if not ns_ok:
        for line in ns_lines:
            print(line)
        print()
        print("结论：spec 的 no_source 清单不合格（exit 2）")
        return 2

    # ── ②③ 参照：工作区 + git HEAD ──────────────────────────────────────────
    repo_root, gerr = git_repo_root()
    if not repo_root:
        print("失败：找不到 git 仓根，无法比对「已提交产物」：%s" % gerr)
        print()
        print("结论：跑不起来（exit 2）")
        return 2
    rel_reports = os.path.relpath(os.path.abspath(args.reports), repo_root).replace(os.sep, "/")

    refs = {}
    for n in names:
        wp = os.path.join(args.reports, n)
        if not os.path.exists(wp):
            print("失败：产物不存在，无法比对：%s" % wp)
            print()
            print("结论：跑不起来（exit 2）")
            return 2
        rel = rel_reports + "/" + n
        head_bytes, herr = git_head_bytes(repo_root, rel)
        if head_bytes is None:
            print("失败：已提交产物取不到，无法比对「已提交产物」：git show HEAD:%s —— %s" % (rel, herr))
            print()
            print("结论：跑不起来（exit 2）")
            return 2
        refs[n] = {"work": read_bytes(wp), "head": head_bytes, "rel": rel}

    # ── 重建到临时目录（门已经自己核对过真源，不再指望生成器的 --cross-check）──
    tmp = tempfile.mkdtemp(prefix="artifact_verify_")
    after = os.path.join(tmp, "after")
    os.makedirs(after)
    try:
        cmd = [sys.executable, BUILDER, "--spec", args.spec, "--outdir", after]
        if args.png:
            cmd.append("--png")
        proc = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            print("失败：生成脚本退出码 %d" % proc.returncode)
            print(proc.stdout.decode("utf-8", "replace"))
            print()
            print("结论：跑不起来（exit 2）")
            return 2

        results = []
        for n in names:
            new_bytes = read_bytes(os.path.join(after, n))
            cmp_work = compare_pair(n, refs[n]["work"], new_bytes, "A 工作区")
            cmp_head = compare_pair(n, refs[n]["head"], new_bytes, "B 已提交")
            results.append((n, cmp_work, cmp_head))

        # ── PNG（可选；Chrome 版本敏感，默认不参与门禁）────────────────────
        png_results = []
        if args.png:
            for n in names:
                png = n[:-len(".html")] + ".png"
                new_png = os.path.join(after, png)
                if not os.path.exists(new_png):
                    png_results.append((png, "重建未产出 PNG", False))
                    continue
                new_bytes = read_bytes(new_png)
                for label, key in (("A 工作区", "work"), ("B 已提交", "head")):
                    if key == "work":
                        src = os.path.join(args.reports, png)
                        ref_bytes = read_bytes(src) if os.path.exists(src) else None
                    else:
                        ref_bytes, _ = git_head_bytes(repo_root, refs[n]["rel"][:-len(".html")] + ".png")
                    if ref_bytes is None:
                        png_results.append((png, "%s：参照 PNG 不存在，跳过" % label, None))
                        continue
                    same = ref_bytes == new_bytes
                    png_results.append((png, "%s：%s" % (label, "逐字节相同" if same else
                                                       "不同（%d B vs %d B）"
                                                       % (len(ref_bytes), len(new_bytes))), same))

        # ── 汇总 ───────────────────────────────────────────────────────────
        content_ok = all(c["ok_text"] and c["ok_markup"] and c["ok_style"]
                          for _, cw, ch in results for c in (cw, ch))
        byte_ok = all(c["ok_byte"] for _, cw, ch in results for c in (cw, ch))
        png_bad = any(ok is False for _, _, ok in png_results)
        png_ok = not png_bad
        if args.mode == "content":
            gate = content_ok
        elif args.mode == "byte":
            gate = byte_ok and png_ok
        else:
            gate = content_ok and byte_ok and png_ok

        if not args.quiet:
            print("重建一致断言（票 #79）· 判据=%s" % args.mode)
            print("真源：spec ↔ pilot/out/结果JSON_*.json")
            for line in src_lines:
                print("  " + line)
            for line in ns_lines:
                print("  " + line)
            print("参照 A（工作区）：%s（只读，未改动）" % args.reports)
            print("参照 B（已提交）：git HEAD:%s（git show，在仓根 %s 下执行）"
                  % (rel_reports, repo_root))
            print("重建：%s" % after)
            print()
            for n, cw, ch in results:
                print("· %s" % n)
                for label, c in (("A 工作区", cw), ("B 已提交", ch)):
                    same = c["ok_text"] and c["ok_markup"] and c["ok_style"] and c["ok_byte"]
                    state = "一致" if same else "不一致"
                    print("  [%s] %s" % (label, state))
                    for line in c["notes"]:
                        print("    " + line)
            for png, note, ok in png_results:
                print("· %s —— %s" % (png, note))
            print()

        if gate:
            print("结论：一致（exit 0）")
            return 0
        print("结论：不一致（exit 1）")
        return 1
    finally:
        if args.keep:
            print("临时目录保留：%s" % tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
