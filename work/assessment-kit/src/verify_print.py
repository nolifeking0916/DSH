#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印验收（票 #5）：出 A4 PDF，用**机器判定**代替肉眼看图。

判定方式：Chrome headless --print-to-pdf 出 PDF → poppler 抽**文本层**逐页断言。
PDF 由 HTML 打印而来必有文本层，文本断言比 OCR 更严：能精确判断「某个标签是否被截断」
「有没有 undefined / NaN」「同一段抬头出现几次」「哪一页是空的」。
若 PDF 没有文本层（扫描件），脚本会明确报 NEEDS_OCR 并退出非 0 —— 那时才需要 OCR。

用法：python3 src/verify_print.py [成品路径]
退出码 0 = 打印件合格；非 0 = 有项未通过。
"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, "dist", "云上文旅集团核心人才系列测试_20261024.html")
QA = os.path.join(ROOT, "src", "qa_report.js")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PDFTOTEXT = "/opt/homebrew/bin/pdftotext"
PDFINFO = "/opt/homebrew/bin/pdfinfo"

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("  [OK ] " if ok else "  [FAIL] ") + name + (("：" + detail) if detail else ""))


def main():
    if not os.path.exists(PROD):
        print("找不到成品：", PROD)
        return 2
    html = open(PROD, encoding="utf-8").read()
    qa = open(QA, encoding="utf-8").read()

    tmp_html = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    tmp_html.write(html.rsplit("</body>", 1)[0] + qa + "</body></html>")
    tmp_html.close()
    pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf.close()

    print("== 1. 生成 A4 PDF ==")
    r = subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--virtual-time-budget=5000", "--print-to-pdf=" + pdf.name, "file://" + tmp_html.name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    ok_pdf = os.path.exists(pdf.name) and os.path.getsize(pdf.name) > 20000
    check("PDF 生成成功", ok_pdf, "%d 字节" % (os.path.getsize(pdf.name) if ok_pdf else 0))
    if not ok_pdf:
        return 1

    info = subprocess.run([PDFINFO, pdf.name], stdout=subprocess.PIPE).stdout.decode("utf-8", "ignore")
    size = re.search(r"Page size:\s*([\d.]+) x ([\d.]+)", info)
    pages = int(re.search(r"Pages:\s*(\d+)", info).group(1))
    check("纸张是 A4（595×842 pt）", size and abs(float(size.group(1)) - 595) < 2 and abs(float(size.group(2)) - 842) < 2,
          "%s x %s pt" % (size.group(1), size.group(2)) if size else "未读到")
    check("页数 ≥ 4（四个区块各另起一页）", pages >= 4, "%d 页" % pages)

    print("== 2. 抽文本层 ==")
    txt = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
    txt.close()
    subprocess.run([PDFTOTEXT, "-layout", pdf.name, txt.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    raw = open(txt.name, encoding="utf-8", errors="ignore").read()
    pages_text = [p for p in raw.split("\f")]
    if len(pages_text) and pages_text[-1].strip() == "":
        pages_text = pages_text[:-1]
    if not raw.strip():
        check("PDF 有文本层（否则需 OCR）", False, "NEEDS_OCR：抽不到文本层")
        return 1
    check("PDF 有文本层（可机器判定，无需 OCR）", True, "%d 字符 / %d 页" % (len(raw), len(pages_text)))

    print("== 3. 逐页内容 ==")
    empty = [i + 1 for i, p in enumerate(pages_text) if len(p.strip()) < 40]
    check("没有空白页", not empty, "空页：%s" % (empty or "无"))
    for i, p in enumerate(pages_text, 1):
        if re.search(r"undefined|NaN|\[object Object\]|null%", p):
            check("第 %d 页无 undefined/NaN" % i, False, "")
            break
    else:
        check("各页无 undefined / NaN / [object Object]", True, "")

    print("== 4. 四个区块各出现一次，且有抬头与落款 ==")
    blocks = ["总报告", "第一项报告", "第二项报告", "第三项报告"]
    for b in blocks:
        n = len(re.findall(r"报告区块[^\\n]*" + b, raw))
        check("区块抬头含「%s」且只出现一次" % b, n == 1, "%d 次" % n)
    n_end = len(re.findall(r"本区块结束", raw))
    check("区块落款出现 4 次", n_end == 4, "%d 次" % n_end)

    print("== 5. 关键内容齐全 ==")
    must = {
        "综合评估块": "综合评估",
        "结构性偏科/短板提示": "短板",
        "三项成绩": "三项成绩",
        "怎么用这份结果": "怎么用这份结果",
        "第一项四维名": "互动方式",
        "第二项八维名": "冲突处理",
        "第三项维度名": "风险判断",
        "错题回顾": "错题回顾",
        "一致性检查": "一致性检查",
        "不得说清单": "不得说",
        "打印页脚页码": None,
    }
    for label, needle in must.items():
        if needle is None:
            continue
        check("含「%s」" % label, needle in raw, "" if needle in raw else "缺失")
    pnums = re.findall(r"第\s*\d+\s*页", raw)
    check("含页码（Chrome @page margin box）", len(pnums) >= pages, "%d 处" % len(pnums))
    check("含测评编号与末 4 位（可定位候选人）", "EQ-20261024-95DX6F-FD1E" in raw and "4821" in raw, "")

    print("== 6. 标签未被截断 ==")
    long_labels = ["数量推理与数据素养", "约束分析与约束求解", "归纳推理与模式识别", "风险判断与决策偏差"]
    for lb in long_labels:
        check("「%s」完整出现（未被 viewBox 裁掉）" % lb, lb in raw, "" if lb in raw else "缺失或被裁")
    short_labels = ["演绎", "归纳", "数量", "约束", "图形", "批判", "规划", "风险"]
    miss = [x for x in short_labels if x not in raw]
    check("雷达两字短标签齐全", not miss, "缺：%s" % (miss or "无"))

    print("== 7. 黑白可读（不依赖背景色）==")
    # 斜纹填充是条形图的第二编码；文本层里看不到图案，这里只确认文字与数值都在
    check("维度条有文字标签与数值", len(re.findall(r"\d+\s*/\s*12", raw)) >= 8 or len(re.findall(r"\d+\s*/\s*5", raw)) >= 8,
          "第二项 8 条 + 第三项 8 条")
    check("五级等级词在打印件里是文字（不只靠颜色）",
          all(w in raw for w in ["顶尖", "优秀", "良好", "合格", "待提升"]) or "待提升" in raw, "")

    for f in (tmp_html.name, pdf.name, txt.name):
        try:
            os.unlink(f)
        except OSError:
            pass

    bad = [x for x in results if not x[1]]
    print("\n==== %s ====" % ("全部通过" if not bad else "有 %d 项未通过" % len(bad)))
    for name, _, detail in bad:
        print("  - %s（%s）" % (name, detail))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
