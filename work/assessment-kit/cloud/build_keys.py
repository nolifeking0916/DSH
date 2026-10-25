#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成云函数侧的「答案键」载荷（票 #26 · 维护者 2026-10-25 裁定 Q1=B）。

为什么需要它：自助云版要让**候选人读不到答案**，判据与计分必须留在服务端。
浏览器只发「选了哪一端」，云函数拿这里的锚点算分。

产出两样东西：
    cloud/functions/assessment/keys.json  ← 服务端专属载荷（不出浏览器）
    cloud/functions/assessment/report.js  ← src/modules/report.js 的副本（服务端复用同一段计分码）

关键设计：**服务端不重写一遍计分**。
云函数在 vm 沙箱里跑与客户端**逐字节相同**的 report.js，只是喂给它的 __DATA__ 换成服务端那份。
⇒ 两边逻辑不可能漂移；唯一可能分歧的是数据，而数据由 cloud/verify_scores.js 逐格验。

口径纪律：
  · 数据来源用 `src/build.py` 的 build_data()，**不自己再解析一遍** ——
    客户端算分用的就是它产出的那份数据，服务端必须与它同源。
  · 只抽算分必需的字段：题干、判据释义（rationale）、理论出处不进服务端载荷。

用法：python3 cloud/build_keys.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FUNC_DIR = os.path.join(HERE, "functions", "assessment")


def load_build_module():
    """加载 src/build.py 并复用它的 build_data()（保证与客户端同源）。"""
    path = os.path.join(ROOT, "src", "build.py")
    spec = importlib.util.spec_from_file_location("kb_build", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_keys():
    """产出与客户端同构的 __DATA__，但只含算分必需字段。"""
    data = load_build_module().build_data()
    return {
        "m1": {
            "meta": data["m1"]["meta"],
            "items": [{"id": it["id"], "dim": it["dim"], "anchor": it["anchor"]}
                      for it in data["m1"]["items"]],
        },
        "eq": {
            "dimensions": data["eq"]["dimensions"],
            "self_items": [{"id": x["id"], "dimension": x["dimension"], "reverse": bool(x.get("reverse"))}
                           for x in data["eq"]["self_items"]],
            "sjt": [{"id": x["id"], "dimension": x["dimension"], "answer": x.get("answer"),
                     "second": x.get("second"), "third": x.get("third"),
                     "scored": x.get("scored", True), "pair": x.get("pair") or ""}
                    for x in data["eq"]["sjt"]],
        },
        "m3": {
            "meta": data["m3"]["meta"],
            "dims": data["m3"]["dims"],
            "questions": [{"id": q["id"], "dim": q["dim"], "difficulty": q.get("difficulty"),
                           "stem": q.get("stem"), "answer": q.get("answer"), "explain": q.get("explain") or ""}
                          for q in data["m3"]["questions"]],
        },
    }


def dump_client_data(data):
    """把客户端那份完整 __DATA__ 落到临时目录，供 cloud/verify_scores.js 做交叉验算。

    这份数据**含答案键**，只用于本地验算，不进云函数包、不进浏览器。
    """
    out_dir = os.path.join(HERE, "out")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "client_data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    return path


def copy_report():
    """把客户端的 report.js + copy.js 复制到云函数包内（服务端跑同一段码）。

    copy.js 也要：report.js 在模块加载时就读 window.__COPY__ 的口径文案
    （如 calibAbs / calibRef），缺了会在加载那一刻炸。
    """
    src = os.path.join(ROOT, "src", "modules", "report.js")
    dst = os.path.join(FUNC_DIR, "report.js")
    shutil.copyfile(src, dst)
    csrc = os.path.join(ROOT, "src", "data", "copy.js")
    cdst = os.path.join(FUNC_DIR, "copy.js")
    shutil.copyfile(csrc, cdst)
    h = hashlib.sha256(open(src, "rb").read()).hexdigest()[:12]
    return h


def main():
    data = load_build_module().build_data()
    keys = build_keys()
    os.makedirs(FUNC_DIR, exist_ok=True)
    out = os.path.join(FUNC_DIR, "keys.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(keys, f, ensure_ascii=False, separators=(",", ":"))
    h = copy_report()
    cd = dump_client_data(data)
    print("已生成 %s（%.1f KB）" % (out, os.path.getsize(out) / 1024))
    print("已导出客户端数据（仅供交叉验算）→ %s" % cd)
    print("已同步 report.js（sha256 前 12 位 %s）→ %s" % (h, os.path.join(FUNC_DIR, "report.js")))
    print("  m1 锚点 %d 条 · m2 自评 %d + 情境 %d（计分题 %d）· m3 推理 %d 题" % (
        len(keys["m1"]["items"]), len(keys["eq"]["self_items"]), len(keys["eq"]["sjt"]),
        sum(1 for x in keys["eq"]["sjt"] if x["scored"]), len(keys["m3"]["questions"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
