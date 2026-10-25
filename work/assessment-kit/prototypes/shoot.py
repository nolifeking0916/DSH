#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 390 CSS px 手机视口截图（Chrome 最小窗口宽 500，故用 iframe 包一层再裁剪）。"""
import os, subprocess, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = "file://" + os.path.join(HERE, "candidate-flow-prototype.html")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = os.path.join(HERE, "shots")
W = 390

def shoot(name, variant, screen, height=1400, extra=""):
    os.makedirs(OUT, exist_ok=True)
    wrap = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;background:#fff}}iframe{{width:{W}px;height:{height}px;border:0;display:block}}
</style></head><body><iframe src="{PROTO}?variant={variant}&screen={screen}&bar=0{extra}"></iframe></body></html>"""
    wp = f"/tmp/wrap_{name}.html"
    open(wp, "w", encoding="utf-8").write(wrap)
    png = f"/tmp/shot_{name}.png"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=2", "--virtual-time-budget=2500",
                    f"--window-size=500,{height}", f"--screenshot={png}", f"file://{wp}"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    im = Image.open(png)
    im.crop((0, 0, W * 2, im.size[1])).save(os.path.join(OUT, f"{name}.png"))
    print("  %-18s %s" % (name, Image.open(os.path.join(OUT, f'{name}.png')).size))

if __name__ == "__main__":
    print("按 390 CSS px 视口截图：")
    shoot("A-start", "A", "start")
    shoot("A-consent", "A", "consent", 2700)
    shoot("A-quiz-AB", "A", "quiz", extra="&qtype=0")
    shoot("A-quiz-scale", "A", "quiz", extra="&qtype=1")
    shoot("A-quiz-MC", "A", "quiz", extra="&qtype=2")
    shoot("A-done", "A", "done")
    shoot("B-start", "B", "start")
    shoot("B-consent", "B", "consent", 2700)
    shoot("B-quiz-MC", "B", "quiz", extra="&qtype=2")
    shoot("B-done", "B", "done")
    shoot("C-start", "C", "start")
    shoot("C-consent", "C", "consent", 2700)
    shoot("C-quiz-MC", "C", "quiz", extra="&qtype=2")
    shoot("C-done", "C", "done")
