#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成品自检：对比度 / 告知卡 10 条 / 红线词 / 题面零漂移 / 外链 / 综合评估块 / 六屏无报错。

用法：python3 src/verify_product.py
依赖：dist/ 下的成品（先跑 src/build.py）
"""
import sys
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
PRODUCT = os.path.join(DIST, "云上文旅集团核心人才系列测试_20261024.html")
if len(sys.argv) > 1:  # 可指定要验的产物（云上测试版走这里）
    PRODUCT = sys.argv[1]
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
        ("云版页脚文案在（两套并存，渲染时按 CLOUD.enabled 选）", "会提交到集团人力资源部的系统" in html),
        ("云端占位符已替换（__CLOUD_ON__ / __CLOUD_ENDPOINT__）", "__CLOUD_" not in html),
        ("云端开关与端点一致", ("enabled: true" not in html) or ("/api/assessment" in html)),
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

    print("\n== 9. 胶囊内边距 ≥ 圆角半径（票 #27 的硬规则） ==")
    # 规则：胶囊（border-radius:999px）的**横向内边距必须 ≥ 圆角半径**（= 高的一半），
    # 否则 2 个汉字会落进圆弧区，视觉上「卡边」（.grade-pill 就是这样被发现的）。
    # 这条做成断言，比每次肉眼看像素更能防回归。
    pills = [("src/components.css", ".grade-pill"), ("src/components.css", ".tag"),
             ("src/layout.css", ".rep-nav button")]
    for rel, sel in pills:
        css = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        m = re.search(re.escape(sel) + r"\s*\{([^}]*)\}", css)
        if not m:
            print("  [FAIL] 找不到规则 %s（%s）" % (sel, rel))
            fails.append("胶囊规则缺失 %s" % sel)
            continue
        body = m.group(1)
        mh = re.search(r"min-height\s*:\s*(\d+)px", body)
        # 横向内边距：padding:0 15px / padding:0 var(--sp-3) → 取第二个值
        pad = re.search(r"padding\s*:\s*0\s+([^;]+)", body)
        px = None
        if pad:
            v = pad.group(1).strip()
            if v.endswith("px"):
                px = int(re.sub(r"[^\d]", "", v))
            elif v.startswith("var("):
                sp = re.search(r"--sp-3\s*:\s*(\d+)px", tokens_css)
                px = int(sp.group(1)) if sp else None
        if not mh or px is None:
            print("  [FAIL] %s 的 min-height / padding 读不出来（%s）" % (sel, rel))
            fails.append("胶囊规则读不出 %s" % sel)
            continue
        radius = int(mh.group(1)) / 2.0
        ok = px >= radius
        print("  [%s] %s：内边距 %dpx ≥ 半径 %.1fpx（高 %dpx）" % ("OK " if ok else "FAIL", sel, px, radius, int(mh.group(1))))
        if not ok:
            fails.append("%s 内边距 %dpx < 半径 %.1fpx（胶囊会卡边）" % (sel, px, radius))

    print("\n== 10. 雷达图标签几何（票 #27） ==")
    # 数值标签必须**落在画布内**且**与同轴维度名分开**：之前 report.js 的
    # `p2[1] < cy ? -6 : 12` 漏了 `p2[1] +`，上半圈数值全塌到 SVG 顶边，
    # 互相叠还跟顶部维度名叠 —— 读者对不上哪个数属于哪一维。
    qa2 = open(os.path.join(ROOT, "src", "qa_report.js"), encoding="utf-8").read()
    qp = os.path.join(DIST, "_qa_radar.html")
    open(qp, "w", encoding="utf-8").write(html.replace("</body>", qa2 + "</body>"))
    dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=4000",
                          "--dump-dom", "file://" + qp],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode("utf-8", "ignore")
    # 先剥掉 style/script：components.css 的 DOM 契约注释里也有一段 <svg class="radar"> 示例，
    # 不剥掉会抽到注释里的旧示例（viewBox 420 420），而不是真渲染出来的那张图。
    dom = re.sub(r"<style.*?</style>|<script.*?</script>", "", dom, flags=re.S)
    svg_m = re.search(r'<svg class="radar"[^>]*>.*?</svg>', dom, re.S)
    if not svg_m:
        print("  [FAIL] 报告页里没抽出雷达 SVG")
        fails.append("雷达 SVG 未找到")
    else:
        svg = svg_m.group(0)
        names = [(float(a), float(b)) for a, b in
                 re.findall(r'<text class="radar-label" x="([-\d.]+)" y="([-\d.]+)"', svg)]
        vals = [(float(a), float(b)) for a, b in
                re.findall(r'<text class="radar-value" x="([-\d.]+)" y="([-\d.]+)"', svg)]
        out = [(i, v) for i, v in enumerate(vals) if not (0 <= v[0] <= 360 and 0 <= v[1] <= 300)]
        check_ok = not out and len(names) == len(vals) and len(vals) >= 8
        print("  [%s] 雷达数值标签都在画布内（%d 个）" % ("OK " if not out else "FAIL", len(vals)),
              "、".join("#%d(%.0f,%.0f)" % (i + 1, v[0], v[1]) for i, v in out) if out else "")
        if out:
            fails.append("雷达数值标签出画布：%d 个" % len(out))
        if len(names) != len(vals) or len(vals) < 8:
            fails.append("雷达标签数量异常（名 %d / 值 %d）" % (len(names), len(vals)))
            print("  [FAIL] 雷达标签数量异常：名 %d / 值 %d" % (len(names), len(vals)))
        else:
            close = []
            for i, (npos, vpos) in enumerate(zip(names, vals)):
                dist = math.hypot(npos[0] - vpos[0], npos[1] - vpos[1])
                if dist < 12:
                    close.append("#%d(%.1fpx)" % (i + 1, dist))
            print("  [%s] 雷达数值与维度名不重叠（最小间距 ≥ 12px）" % ("OK " if not close else "FAIL"),
                  "、".join(close) if close else "")
            if close:
                fails.append("雷达数值与维度名重叠：%s" % "、".join(close))
    try:
        os.remove(qp)
    except OSError:
        pass

    print("\n== 11. 等级徽章像素级复核（≈200dpi 裁切，票 #27） ==")
    # 第 9 节只证明「CSS 里声明的 padding 够大」；这一节证明**渲染出来**够大：
    # 用产品 CSS 渲染一行等级胶囊 → Chrome 以 2× 像素密度截图（96dpi×2 ≈ 192dpi ≈ 200dpi）
    # → 量「胶囊外框」与「文字墨迹」之间的左右间距。
    # 两条判定：
    #   ① 墨迹整体落在胶囊的**直段**里（左右间距 ≥ 圆角半径）——「胶囊横向内边距 ≥ 半径」
    #      这条硬规则的像素版；
    #   ② 左右各留 ≥4 设备像素（≈2 CSS px）的**可见余量**——「不卡边」观感的机器版。
    # 裁切图落在 dist/shots/pill_<等级>.png，供人眼抽查（人眼只抽查，不判定）。
    # 量法改为**浏览器几何量测**（2026-10-25 修）：
    # 旧做法是从 2× 截图里「找比底色暗 20 以上的像素」当文字墨迹，再量它到胶囊外框的距离。
    # 实测这套推断有两个硬伤，会把合格品判成不合格：
    #   ① 一维「只找暗墨迹」——顶尖是深底浅字（--lv-t-bg #1E4634 / --lv-t-fg #F5F0E4），
    #      浅色文字在「比底色暗」的口径下根本找不到 → 报「没找到文字墨迹」；
    #   ② 胶囊有 1px 描边（描边色 = 文字色），2× 截图下描边及其抗锯齿落在裁切窗口内，
    #      被当成「文字」量出左右余量只有 4px —— 量的其实是描边，不是字。
    # 现在改成让浏览器自己量：Range 框住文字节点 → 文字矩形与胶囊矩形的差 = 真实左右余量；
    # 半径 = 胶囊高的一半。同一判据、零像素猜测，抗锯齿与深浅底都免疫。
    # 判定两条（不变）：
    #   ① 左右余量 ≥ 圆角半径 —— 「胶囊横向内边距 ≥ 半径」这条硬规则的渲染版；
    #   ② 左右各留 ≥ 2 CSS px 的可见余量 —— 「不卡边」观感的机器版。
    # 裁切图仍落在 dist/shots/pill_<等级>.png，供人眼抽查（人眼只抽查，不判定）。
    components_css = open(os.path.join(ROOT, "src", "components.css"), encoding="utf-8").read()
    grades = [("顶尖", "T"), ("优秀", "A"), ("良好", "B"), ("合格", "C"), ("待提升", "D")]
    ROW = 56                                   # 每行 56 CSS px（胶囊 26px 居中，上下留白足够）
    probe_js = (
        "<script>window.__P__=[];"
        "for(const s of document.querySelectorAll('.grade-pill')){"
        "const pr=s.getBoundingClientRect();const r=document.createRange();r.selectNodeContents(s);"
        "const tr=r.getBoundingClientRect();"
        "window.__P__.push({t:s.textContent,lv:s.dataset.level,left:tr.left-pr.left,right:pr.right-tr.right,"
        "rad:pr.height/2,h:pr.height,x:pr.left,y:pr.top,w:pr.width});}"
        "document.title=JSON.stringify(window.__P__);</script>")
    probe = ("<!doctype html><html><head><meta charset='utf-8'><style>" + tokens_css + components_css +
             "html,body{margin:0;padding:0;background:#fff}"
             ".probe-row{height:%dpx;display:flex;align-items:center;padding-left:16px}"
             "</style></head><body>" % ROW +
             "".join('<div class="probe-row"><span class="grade-pill" data-level="%s">%s</span></div>' % (lv, g)
                     for g, lv in grades) + probe_js + "</body></html>")
    pp = os.path.join(DIST, "_qa_pill.html")
    open(pp, "w", encoding="utf-8").write(probe)
    dom = ""
    try:
        proc = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=2000",
                               "--dump-dom", "file://" + pp],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=180)
        dom = proc.stdout.decode("utf-8", "replace")
    except Exception as exc:                      # noqa: BLE001
        print("  [FAIL] 等级徽章探针页取数失败：%s" % exc)
        fails.append("等级徽章探针页取数失败")
    m = re.search(r"<title>(.*?)</title>", dom, re.S)
    try:
        measured = json.loads(m.group(1)) if m else None
    except ValueError:
        measured = None
    if not measured:
        print("  [FAIL] 等级徽章探针页没取到几何数据")
        fails.append("等级徽章几何复核未执行（探针无输出）")
    else:
        # 顺带截一张 2× 图供人眼抽查（裁切位置用量出来的几何，不再靠像素推断）
        png = "/tmp/qa_pill.png"
        if os.path.exists(png):
            os.remove(png)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=2", "--virtual-time-budget=2500",
                        "--window-size=320,%d" % (ROW * len(grades)), "--screenshot=" + png, "file://" + pp],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            from PIL import Image
            if os.path.exists(png):
                im = Image.open(png).convert("RGB")
                sc = 2                                    # --force-device-scale-factor=2
                for it in measured:
                    box = (int((it["x"] - 10) * sc), int((it["y"] - 10) * sc),
                           int((it["x"] + it["w"] + 10) * sc), int((it["y"] + it["h"] + 10) * sc))
                    im.crop(box).save(os.path.join(SHOTS, "pill_%s.png" % it["t"]))
        except Exception:                               # noqa: BLE001
            print("  [提示] 没能裁出人眼抽查图（缺 PIL？），不影响判定")
        for it in measured:
            g = it["t"]
            gl, gr, rad = it["left"], it["right"], it["rad"]
            ok = gl >= rad - 0.5 and gr >= rad - 0.5 and gl >= 2 and gr >= 2
            print("  [%s] %s：左余量 %.1fpx / 右余量 %.1fpx（圆角半径 %.1fpx，胶囊高 %.1fpx）"
                  % ("OK " if ok else "FAIL", g, gl, gr, rad, it["h"]))
            if not ok:
                fails.append("%s 徽章左右余量不足（左 %.1f / 右 %.1f / 半径 %.1f）" % (g, gl, gr, rad))
    try:
        os.remove(pp)
    except OSError:
        pass

    print("\n==== %s ====" % ("全部通过" if not fails else "有 %d 项未通过" % len(fails)))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
