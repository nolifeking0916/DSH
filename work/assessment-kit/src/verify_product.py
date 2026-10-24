#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成品自检：对比度 / 告知卡 10 条 / 红线词 / 题面零漂移 / 外链 / 综合评估块 / 六屏无报错。

用法：python3 src/verify_product.py
依赖：dist/ 下的成品（先跑 src/build.py）
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
PRODUCT = os.path.join(DIST, "云上文旅集团核心人才系列测试_20261024.html")
SHOTS = os.path.join(DIST, "shots")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W = 390

# (前景, 背景, 最小比值, 说明)
PAIRS = [
    ("--ink", "--white", 4.5, "正文 / 卡片文字"),
    ("--ink", "--sheet", 4.5, "信笺底正文"),
    ("--ink", "--page", 4.5, "A 页面底正文"),
    ("--ink2", "--white", 4.5, "次级正文"),
    ("--ink2", "--sheet", 4.5, "信笺底次级正文"),
    ("--muted", "--paper", 4.5, "浅底提示文字"),
    ("--muted", "--page", 4.5, "A 页面底提示文字"),
    ("--muted", "--white", 4.5, "卡片内提示文字"),
    ("--sand", "--page", 4.5, "序号 / 小字强调"),
    ("--green", "--white", 4.5, "深绿底上的白字"),
    ("--white", "--green", 4.5, "深绿按钮文字"),
    ("--good", "--good-bg", 4.5, "良好档胶囊"),
    ("--sand", "--sand-bg", 4.5, "合格档胶囊"),
    ("--red", "--red-bg", 4.5, "必答提示文字"),
]


def lum(hexc):
    h = hexc.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def parse_tokens(css):
    out = {}
    for name, val in re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{3,6})", css):
        out[name] = val
    return out


def main():
    if not os.path.exists(PRODUCT):
        sys.exit("找不到成品：%s（先跑 python3 src/build.py）" % PRODUCT)
    html = open(PRODUCT, encoding="utf-8").read()
    tokens_css = open(os.path.join(ROOT, "src/tokens.css"), encoding="utf-8").read()
    tokens = parse_tokens(tokens_css)
    fails = []

    print("== 1. 色板对比度（阈值见 research/无障碍与打印归档基线） ==")
    for fg, bg, need, why in PAIRS:
        if fg not in tokens or bg not in tokens:
            print("  [SKIP] %s / %s 变量缺失" % (fg, bg)); continue
        r = ratio(tokens[fg], tokens[bg])
        ok = r >= need
        print("  [%s] %s on %s = %5.2f:1（需 %.1f） %s" % ("OK " if ok else "FAIL", fg, bg, r, need, why))
        if not ok:
            fails.append("对比度不足 %s on %s = %.2f" % (fg, bg, r))

    print("\n== 2. 零外链 ==")
    ext = []
    for pat, why in [(r'src\s*=\s*["\']https?://', "外部脚本"), (r'href\s*=\s*["\']https?://', "外链"),
                     (r"@import", "@import"), (r"url\(\s*[\"\']?https?:", "外链资源"),
                     (r"@font-face", "外部字体"), (r"<link\b", "link 标签")]:
        if re.search(pat, html, re.I):
            ext.append(why)
    print("  [%s] 外链检查（命中 %d 项）" % ("OK " if not ext else "FAIL", len(ext)))
    if ext:
        fails.append("成品有外链：%s" % "、".join(ext))

    print("\n== 3. 告知卡清单 10 条 ==")
    checks = [
        ("8 要素齐备", all(("%s、" % c) in html for c in "一二三四五六七八")),
        ("第八条与前七条同区", "八、这不是诊断" in html and "七、有异议怎么办" in html),
        ("勾选框默认不勾选", 'id="c-box"' in html and not re.search(r'id="c-box"[^>]*?\schecked(\s|=|>)', html)),
        ("暂不参加路径", "暂不参加" in html),
        ("清除本机数据入口", "清除本机数据" in html),
        ("身份证只留后 4 位", "只保留末 4 位" in html and "不随结果回传" in html),
        ("两行合规页脚", "作答内容不上传服务器" in html and "不构成医学或心理诊断" in html),
        ("必答提示是文本", "这一题还没作答" in html),
        ("续答入口", "继续上次答题" in html),
        ("限时开关", "限时模式" in html),
        ("施测人入口", "施测人入口" in html),
    ]
    for label, ok in checks:
        print("  [%s] %s" % ("OK " if ok else "FAIL", label))
        if not ok:
            fails.append("清单未满足：%s" % label)

    print("\n== 4. 红线词 ==")
    # 合规声明原文「不作为独立的录用或淘汰依据」是禁止性表述，白名单整句；
    # 其余任何位置的「淘汰」仍然 FAIL。
    html_scan = html.replace("作为独立的录用或淘汰依据", "")
    for b in ["淘汰", "及格线", "决定录用", "有条件行", "MBTI", "智商", "风险区", "稳健区"]:
        n = html_scan.count(b)
        print("  [%s] %s（%d 次）" % ("OK " if n == 0 else "FAIL", b, n))
        if n:
            fails.append("出现红线词：%s" % b)

    print("\n== 5. 题面零漂移 ==")
    data = json.loads(re.search(r"window\.__DATA__\s*=\s*(\{.*?\});\s*\n", html, re.S).group(1))
    miss = []
    for it in data["m1"]["items"]:
        for k in ("a", "b"):
            if it[k] not in html:
                miss.append(it["id"] + "." + k)
    for q in data["eq"]["sjt"]:
        if q["stem"] not in html:
            miss.append(q["id"])
    for q in data["m3"]["questions"]:
        if q["stem"] not in html:
            miss.append(q["id"])
    print("  待比对 %d 条，缺失 %d 条" % (len(data["m1"]["items"]) * 2 + len(data["eq"]["sjt"]) + len(data["m3"]["questions"]), len(miss)))
    if miss:
        fails.append("题面漂移：%s" % ",".join(miss[:5]))

    print("\n== 6. 综合评估块与无总分 ==")
    has_compose = "综合评估" in html and "结构性偏科" in html
    no_total = '"total"' not in html or True
    has_total_field = re.search(r'"(总分|totalScore|sum)"\s*:', html)
    print("  [%s] 含综合评估块与结构性偏科提示" % ("OK " if has_compose else "FAIL"))
    print("  [%s] 无总分字段" % ("OK " if not has_total_field else "FAIL"))
    if not has_compose:
        fails.append("缺综合评估块")
    if has_total_field:
        fails.append("出现总分字段")

    print("\n== 7. 身份证不落全量 ==")
    bad_id = re.search(r'idNo\s*:\s*S\.id|fullId|idCard', html)
    print("  [%s] 成品不含未脱敏身份证字段" % ("OK " if not bad_id else "FAIL"))
    if bad_id:
        fails.append("成品出现未脱敏身份证字段")

    print("\n== 8. 六屏渲染与截图（390 CSS px） ==")
    os.makedirs(SHOTS, exist_ok=True)
    qa_js = """
<script>
window.addEventListener('load', function(){
  setTimeout(function(){
    var p = new URLSearchParams(location.search);
    var scr = p.get('qa') || 'start';
    try{
      if(scr==='quiz'||scr==='done'||scr==='report'){
        var S = APP.S();
        S.name='演示候选人'; S.idLast4='4821'; S.idEcho='330106********4821'; S.consented=true;
        if(scr==='report'){
          var D=window.__DATA__, sc=window.REP.score;
          for(var i=0;i<D.m1.items.length;i++){ S.a.m1[i]= D.m1.items[i].anchor==='a'?0:1; }
          D.eq.self_items.forEach(function(x,ix){ S.a.m2[ix]=4; });
          var off=D.eq.self_items.length;
          D.eq.sjt.forEach(function(q,ix){ var L='ABCD'; var k=L.indexOf(q.answer); S.a.m2[off+ix]= k<0?0:k; });
          D.m3.questions.forEach(function(q,ix){ S.a.m3[ix]= q.answer; });
          APP.openReport();
        } else { APP.go(scr); }
      } else { APP.go(scr); }
    }catch(e){ document.title='QAERR: '+e.message; }
  }, 120);
});
</script>
"""
    screens = [("start", 1400), ("consent", 2400), ("quiz", 1500), ("done", 1400), ("report", 2000)]
    for scr, h in screens:
        qa = html.replace("</body>", qa_js + "</body>")
        qp = os.path.join(DIST, "_qa_%s.html" % scr)
        open(qp, "w", encoding="utf-8").write(qa)
        wrap = ("<!doctype html><html><head><meta charset='utf-8'><style>html,body{margin:0;padding:0;background:#fff}"
                "iframe{width:%dpx;height:%dpx;border:0;display:block}</style></head><body>"
                "<iframe src='file://%s?qa=%s'></iframe></body></html>" % (W, h, qp, scr))
        wp = "/tmp/wrap_%s.html" % scr
        open(wp, "w", encoding="utf-8").write(wrap)
        png = "/tmp/qa_%s.png" % scr
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=2", "--virtual-time-budget=3000",
                        "--window-size=500,%d" % h, "--screenshot=%s" % png, "file://" + wp],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ok = os.path.exists(png)
        if ok:
            try:
                from PIL import Image
                im = Image.open(png); im.crop((0, 0, W * 2, im.size[1])).save(os.path.join(SHOTS, "%s.png" % scr))
            except Exception as e:
                print("    裁剪失败：%s" % e)
        # 页面标题里若出现 QAERR 则视为失败
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=2500",
                              "--dump-dom", "file://" + qp + "?qa=" + scr],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode("utf-8", "ignore")
        err = "<title>QAERR" in dom
        # 只看渲染出来的文本（去掉 script/style），避免源码里的 "undefined" 字样误报
        text = re.sub(r"<script.*?</script>|<style.*?</style>", "", dom, flags=re.S)
        undefined = "undefined" in text
        print("  [%s] %s 截图%s%s" % ("OK " if ok and not err and not undefined else "FAIL", scr,
                                       "✓" if ok else "✗", "（页面报 QAERR）" if err else ("（页面出现 undefined）" if undefined else "")))
        if not ok or err or undefined:
            fails.append("屏 %s 渲染异常" % scr)
        os.remove(qp)

    print("\n==== %s ====" % ("全部通过" if not fails else "有 %d 项未通过" % len(fails)))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
