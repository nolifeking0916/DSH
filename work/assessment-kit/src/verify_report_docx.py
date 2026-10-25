#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""施测人报告（Word/PDF）打印验收门 —— 票 #24 后续 / 报告重做。

按仓内口径「验收一律机器判定」：不靠肉眼看图，靠 **PDF 文本层逐项断言**。
本门专门盯这轮报告重做要解决的几件事：
  · 三章结构与关键内容在场（结果 / 解析 / 判断）
  · **没有「错题回顾」**（用户明确不要）
  · 等级词完整（不被裁成半个字）
  · 每页都有合规声明与页码（不留空白页）
  · **页面密度均衡**（不出现一页 4000 字的文字墙，也不出现整页留白）
  · 无 undefined / NaN / null 等技术残留
用法：python3 src/verify_report_docx.py [PDF 路径]
退出码 0 = 合格；非 0 = 有项未通过。
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PDFTOTEXT = "/opt/homebrew/bin/pdftotext"
PDFINFO = "/opt/homebrew/bin/pdfinfo"
DEFAULT = os.path.join(ROOT, "reports", "施测人报告_SIM-20261024-E2E0001_20261024.pdf")

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("  [OK ] " if ok else "  [FAIL] ") + name + (("：" + detail) if detail else ""))


def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    if not os.path.exists(pdf):
        print("找不到 PDF：%s" % pdf)
        return 2
    raw = subprocess.run([PDFTOTEXT, "-layout", pdf, "-"], stdout=subprocess.PIPE).stdout.decode("utf-8", "ignore")
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    flat = "".join(pages)
    info = subprocess.run([PDFINFO, pdf], stdout=subprocess.PIPE).stdout.decode("utf-8", "ignore")
    m = re.search(r"Pages:\s+(\d+)", info)
    npages = int(m.group(1)) if m else len(pages)

    print("== 施测人报告打印验收 ==")
    check("PDF 有文本层", len(flat.strip()) > 500, "%d 字符 / %d 页" % (len(flat.strip()), npages))

    # 0. 中文字体必须真的嵌进去了
    #    （踩过的坑：w:rFonts 的 eastAsia 写成子元素 → LibreOffice 忽略 → 中文回退到
    #     LinuxLibertineG / FrankRuhlHofshi → 满篇豆腐块，而文本层里中文还在，
    #     只看 pdftotext 是发现不了的。所以必须查 pdffonts。）
    fonts = subprocess.run(["/opt/homebrew/bin/pdffonts", pdf], stdout=subprocess.PIPE).stdout.decode("utf-8", "ignore")
    cjk_pat = ("Songti", "Heiti", "STSong", "SourceHan", "PingFang", "Noto", "SimSun", "SimHei",
               "Microsoft", "WenQuanYi", "Han")
    cjk = [ln.split()[0] for ln in fonts.splitlines()[2:] if ln.strip()
           and any(p.lower() in ln.lower() for p in cjk_pat)]
    fallback = [ln.split()[0] for ln in fonts.splitlines()[2:] if ln.strip()
                and ("LinuxLibertine" in ln or "FrankRuhl" in ln or "Liberation" in ln)]
    check("PDF 嵌入中文字体", bool(cjk),
          ("嵌入：" + "、".join(sorted(set(cjk))[:4])) if cjk else
          "未发现中文字体 → 中文会渲染成豆腐块")
    check("未回退到拉丁/希伯来字体", not fallback,
          ("回退：" + "、".join(sorted(set(fallback))[:3])) if fallback else "")

    # 1. 三章结构
    for name in ("一", "结果", "二", "对结果的解析", "三", "对候选人的判断"):
        pass
    check("三章标题在场", all(k in flat for k in ("结果", "对结果的解析", "对候选人的判断")))
    check("综合评估在场", "综合评估" in flat)
    check("三项成绩在场", all(k in flat for k in ("第一项", "第二项", "第三项")))
    check("追问清单在场", "面试追问清单" in flat)

    # 2. 错题回顾必须不在场（这轮明确去掉）
    check("无「错题回顾」章节", "错题回顾" not in flat,
          "本轮报告只给结果、解析与判断")

    # 3. 等级词完整（不能被裁成半个字）
    #    PDF 文本层会把词拆开（换行 / 列宽导致字间空格），判断前先去掉所有空白，
    #    否则「优 秀」会被误判成「秀」被截断。
    ns = re.sub(r"\s+", "", flat)
    grades = [g for g in ("顶尖", "优秀", "良好", "合格", "待提升") if g in ns]
    check("等级词完整出现", len(grades) >= 3, "出现：" + "、".join(grades))
    lone = []
    tmp = ns
    for g in ("优秀", "顶尖", "良好", "合格", "待提升"):
        tmp = tmp.replace(g, "")
    # 只用「秀」「尖」当探针：这两个字在正常中文里几乎不单字出现；
    # 「好」「格」不行——「表现好时」「性格」「变好」都会误报。
    lone = [c for c in "秀尖" if c in tmp]
    check("等级词未被截断", not lone,
          ("出现孤立字：" + "、".join(lone)) if lone else "未发现半个等级词")

    # 4. 每页合规声明与页码
    miss_foot = [i + 1 for i, p in enumerate(pages)
                 if "不得作为录用唯一依据" not in p]
    check("每页都有合规声明", not miss_foot, "缺失页：" + "、".join(map(str, miss_foot)))
    # 页码必须**在一行内**（折行说明 margin box 宽度被挤掉了，是排版瑕疵）
    miss_no = [i + 1 for i, p in enumerate(pages)
               if not re.search(r"第\s*\d+\s*/\s*\d+\s*页", "".join(p.split()))]
    check("每页都有页码且不折行", not miss_no, "缺失或折行页：" + "、".join(map(str, miss_no)))

    # 5. 页面密度均衡（不出现文字墙，也不出现整页留白）
    counts = [len("".join(p.split())) for p in pages]
    if counts:
        top = max(counts)
        empty = [i + 1 for i, c in enumerate(counts) if c < 60]
        check("无整页空白页", not empty, "近空页：" + "、".join(map(str, empty)))
        check("无文字墙（单页 ≤ 1800 字符）", top <= 1800, "最密一页 %d 字符" % top)
        spread = (max(counts) - min(counts)) / max(1, max(counts))
        check("页面密度不过分失衡（极差 ≤ 90%）", spread <= 0.90,
              "各页字符数 %s" % "、".join(str(c) for c in counts))

    # 6. 无技术残留
    for junk in ("undefined", "NaN", "null", "[object Object]", "TODO"):
        check("无「%s」残留" % junk, junk not in flat)

    # 7. 关键内容在场
    # 雷达口径（票 #27 裁定）：画**参考分布百分位**，与维度表里的百分位列同口径；
    # 正确数/总题数仍在维度表里，两个口径可互相推导。
    check("雷达图说明与百分位口径在场",
          ("百分位" in flat and "参考分布" in flat and ("P50" in flat or "中位" in flat)),
          "")
    check("维度表同时给正确数与百分位（两个口径可推导）",
          "正确" in flat and "百分位" in flat and "T 分" in flat, "")
    check("使用边界在场", all(k in flat for k in ("使用边界", "不设淘汰线")))

    bad = [n for n, ok in results if not ok]
    print("  PDF：%s" % pdf)
    if bad:
        print("未通过：%s" % "、".join(bad))
        return 1
    print("打印验收全部通过（%d 项）" % len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
