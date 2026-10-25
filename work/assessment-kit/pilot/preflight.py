#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发卷前预检（票 #26 前置工具）

一条命令把「能不能开始发卷」这件事变成机器判定，避免靠记忆：

    cd work/assessment-kit
    python3 pilot/preflight.py

检查项：
  1. 成品存在性：单文件 H5 在不在、多大、sha256（短）——施测发的是哪一份要说得出
  2. 成品新鲜度：成品 mtime 必须不早于**产品源**（src/ 下的 css/js/数据，**不含** verify_*.py 门脚本）
     ——源改了没重建就发卷，等于测的是旧版
  3. 限时口径探测：成品里有没有「到点自动交卷」标记（limitCut）——只**报**当前是哪套口径，
     不做判断（口径由票 #26 的 Q2 拍板）
  4. 四个自检门：verify_product / verify_compliance / verify_print / verify_limit
  5. 两个新工具的自检：ingest_real.py / analyze_annotations.py
  6. 回收登记表模板：生成到输出目录（pilot/out/ 已被 .gitignore 排除），并打印表头

退出码：0 = 全过（可能带「待决」提示）；1 = 有 FAIL。

口径来源：真人试测作业包_20261024.md §三/§四；票 #26 范围第 2/4/13 条。
本脚本**不改任何既有文件**，只读 + 在 pilot/out/ 里写一份模板。
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # work/assessment-kit
SRC = os.path.join(ROOT, "src")
DIST = os.path.join(ROOT, "dist")
OUTDIR_DEFAULT = os.path.join(HERE, "out")

# 成品：优先取本机 outputs 目录里最新的「核心人才系列测试」单文件（排除旧版备份与打印件）
OUTPUTS = "/Users/leto/WorkBuddy/HR技术中台/outputs"
PRODUCT_NAME_RE = re.compile(r"^云上文旅集团核心人才系列测试_.*\.html$")
EXCLUDE_NAME_RE = re.compile(r"旧版备份")

GATES = [
    ("verify_product", "成品门：对比度/清单/红线词/题面零漂移/五屏截图/胶囊/雷达"),
    ("verify_compliance", "合规门：告知与自动化决策表述"),
    ("verify_print", "打印门：A4 文本层逐页断言"),
    ("verify_limit", "限时口径门：承诺↔实现/到点自动交卷实跑/结果 JSON 字段白名单"),
    ("verify_items", "题库门：逐题选项/判分码 + 212 道题逐题渲染"),
]
TOOLS = [
    ("ingest_real.py", "回收表录入 → 真实作答 JSON"),
    ("analyze_annotations.py", "双人标注/仲裁/锚定审计 → 分歧率与命中率"),
]

# 产品源 = 会被 build.py 内联进单文件的那些文件；门脚本与报告生成器**不算**
def product_sources():
    out = []
    for base, _dirs, files in os.walk(SRC):
        for fn in files:
            p = os.path.join(base, fn)
            if fn.startswith("verify_") or fn.endswith(".py"):
                continue
            out.append(p)
    return out


def pick_product():
    if not os.path.isdir(OUTPUTS):
        return None
    cands = []
    for fn in os.listdir(OUTPUTS):
        if not PRODUCT_NAME_RE.match(fn) or EXCLUDE_NAME_RE.search(fn):
            continue
        p = os.path.join(OUTPUTS, fn)
        if os.path.isfile(p):
            cands.append(p)
    if not cands:
        return None
    return max(cands, key=os.path.getmtime)


def sha_short(path, n=12):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def run(cmd, timeout=600):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "超时（%d 秒）" % timeout, time.time() - t0
    return p.returncode, (p.stdout or "") + (p.stderr or ""), time.time() - t0


def tail(text, lines=2, width=110):
    ls = [l for l in (text or "").strip().splitlines() if l.strip()]
    if not ls:
        return "（无输出）"
    return " / ".join(l.strip()[:width] for l in ls[-lines:])


def main():
    ap = argparse.ArgumentParser(description="发卷前预检（票 #26）")
    ap.add_argument("--product", help="指定成品路径（默认自动在本机 outputs 里找最新一份）")
    ap.add_argument("--out-dir", default=OUTDIR_DEFAULT, help="模板与日志输出目录（默认 pilot/out/）")
    ap.add_argument("--skip-gates", action="store_true", help="跳过四个自检门（快检；不能替代全检）")
    ap.add_argument("--json", action="store_true", help="额外输出 JSON 结果")
    args = ap.parse_args()

    results = []          # (状态, 名称, 说明)   状态 ∈ PASS / FAIL / 待决 / 提示

    # 1) 成品
    product = args.product or pick_product()
    if not product or not os.path.isfile(product):
        results.append(("FAIL", "成品存在", "没找到成品单文件（%s 下没有 %s）" % (OUTPUTS, PRODUCT_NAME_RE.pattern)))
    else:
        size = os.path.getsize(product)
        results.append(("PASS", "成品存在", "%s（%.0f KB · sha256 %s…）" % (os.path.basename(product), size / 1024.0, sha_short(product))))

        # 2) 新鲜度（只比产品源）
        srcs = product_sources()
        if srcs:
            newest = max(srcs, key=os.path.getmtime)
            if os.path.getmtime(product) < os.path.getmtime(newest):
                results.append(("FAIL", "成品新鲜度",
                                "成品早于产品源 %s —— 先重建（src/build.py）再发卷" % os.path.relpath(newest, ROOT)))
            else:
                results.append(("PASS", "成品新鲜度",
                                "成品不早于产品源（最新产品源 %s）" % os.path.relpath(newest, ROOT)))

        # 3) 限时口径（只报不判）
        try:
            with open(product, encoding="utf-8", errors="replace") as f:
                html = f.read()
            has_cut = ("limitCut" in html) or ("自动交卷" in html)
            results.append(("待决" if has_cut else "提示", "限时口径",
                            "成品当前=**B（页面到点自动交卷）**，Q2 未拍板前按两套并存执行"
                            if has_cut else "成品里没找到自动交卷标记 ⇒ 当前= A/C（施测人统一时点收卷）"))
        except OSError as exc:
            results.append(("提示", "限时口径", "读成品失败：%s" % exc))

    # 4) 四个门
    if args.skip_gates:
        results.append(("提示", "自检门", "已按 --skip-gates 跳过 —— 这不是全检"))
    else:
        for name, desc in GATES:
            script = os.path.join(SRC, name + ".py")
            if not os.path.isfile(script):
                results.append(("FAIL", "门 " + name, "脚本不存在"))
                continue
            code, out, dt = run([sys.executable, script])
            ok = (code == 0)
            results.append(("PASS" if ok else "FAIL", "门 " + name,
                            "%s（%s，%.1fs）" % (tail(out), desc, dt)))

    # 5) 两个工具自检
    for name, desc in TOOLS:
        script = os.path.join(HERE, name)
        if not os.path.isfile(script):
            results.append(("FAIL", "工具 " + name, "脚本不存在"))
            continue
        code, out, dt = run([sys.executable, script, "--selftest"])
        results.append(("PASS" if code == 0 else "FAIL", "工具 " + name,
                        "%s（%s，%.1fs）" % (tail(out), desc, dt)))

    # 6) 回收登记表模板
    try:
        os.makedirs(args.out_dir, exist_ok=True)
        tpl = os.path.join(args.out_dir, "回收登记表_模板.csv")
        code, out, _dt = run([sys.executable, os.path.join(HERE, "ingest_real.py"), "--template"])
        if code == 0 and out.strip():
            with open(tpl, "w", encoding="utf-8") as f:
                f.write(out)
            header = [l for l in out.splitlines() if l and not l.startswith("#")]
            results.append(("PASS", "回收表模板", "已生成 %s（表头 %d 列）" % (os.path.relpath(tpl, ROOT),
                                                                          len(header[0].split(",")) if header else 0)))
        else:
            results.append(("FAIL", "回收表模板", "生成失败：%s" % tail(out)))
    except OSError as exc:
        results.append(("FAIL", "回收表模板", "写文件失败：%s" % exc))

    # 汇总
    print("\n=== 发卷前预检（票 #26）===")
    for st, name, msg in results:
        mark = {"PASS": "[OK  ]", "FAIL": "[FAIL]", "待决": "[待决]", "提示": "[提示]"}[st]
        print("  %s %-14s %s" % (mark, name, msg))
    fails = [r for r in results if r[0] == "FAIL"]
    print("\n结论：%s" % ("可以发卷（注意上面标「待决」的口径项）" if not fails
                          else "**有 %d 项未过，先修再发卷**" % len(fails)))
    if args.json:
        import json
        print(json.dumps([{"status": s, "name": n, "detail": d} for s, n, d in results],
                         ensure_ascii=False, indent=2))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
