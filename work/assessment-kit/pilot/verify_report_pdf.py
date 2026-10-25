#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模拟试测报告样例的打印验收 —— 票 #24（模拟版）。

做的是票 #5 那套机器判定的同一件事：Chrome headless 出 A4 PDF → pdftotext 抽
文本层 → 逐页断言。这里断言的是「整卷端到端跑出来的报告，内容真的在纸上」：
四项断言缺一不可。

用法：python3 pilot/verify_report_pdf.py
退出码 0 = 通过；非 0 = 有项未通过。
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
HTML = os.path.join(OUT, "模拟试测_报告样例.html")
PDF = os.path.join(OUT, "模拟试测_报告样例_A4.pdf")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PDFTOTEXT = "/opt/homebrew/bin/pdftotext"

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("  [OK ] " if ok else "  [FAIL] ") + name + (("：" + detail) if detail else ""))


def main():
    if not os.path.exists(HTML):
        print("找不到 %s，先跑 node pilot/run_pilot.mjs" % HTML)
        return 2

    r = subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--virtual-time-budget=5000", "--print-to-pdf=" + PDF, "file://" + HTML],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    ok_pdf = os.path.exists(PDF) and os.path.getsize(PDF) > 10000
    check("PDF 生成成功", ok_pdf,
          "%d 字节" % (os.path.getsize(PDF) if os.path.exists(PDF) else 0))
    if not ok_pdf:
        return 1

    txt = subprocess.run([PDFTOTEXT, PDF, "-"], stdout=subprocess.PIPE).stdout.decode("utf-8", "ignore")
    pages = txt.count("\f") + 1

    check("总报告与综合评估在场", "综合评估" in txt and "总报告" in txt)
    check("三项模块报告在场", all(k in txt for k in ("第一项", "第二项", "第三项")))
    check("五级等级词在场", any(k in txt for k in ("顶尖", "优秀", "良好", "合格", "待提升")))
    check("短板提示在场", "短板" in txt)
    check("合规页脚在场", "不得作为录用唯一依据" in txt)
    check("无 undefined / NaN", "undefined" not in txt and "NaN" not in txt)
    check("分页数合理（3–12 页）", 3 <= pages <= 12, "%d 页" % pages)

    print("  PDF：%s" % PDF)
    bad = [n for n, ok in results if not ok]
    if bad:
        print("未通过：%s" % "、".join(bad))
        return 1
    print("打印验收全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
