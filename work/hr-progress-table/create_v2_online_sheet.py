#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在企业微信在线表格《集团人力近期重点工作进度表》里新建工作表「重点工作进度 v2」。

- 在线表格有 merge 原语，但目标版式**不使用任何合并**（每行独立、维度值逐行重复）
- 新工作表插到第 1 位（打开文档先看到它），原「工作表1」原样保留作底稿
- batchset 单次上限 500 格 → 按 15 列切块写入
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DOCID = "e3_ARsADAagAHQCNea2Y2u1wSA00hrX0"
NEW_SHEET = "重点工作进度 v2"
ROWS = os.path.join(HERE, "rows_v2.json")

COLUMNS = [
    "事项序号", "一级维度（六大模块）", "二级维度（人/流程/成本）",
    "具体事项", "分项", "分项内容简介",
    "进展日期", "进展内容", "开始时间", "完成时间", "当日计划（周计划）",
    "责任人", "负责人", "负责人类型", "协调事项",
]
HEADER_BG = "FFDCE6F1"


def call(service, cmd, payload):
    args = ["wecom-cli", service] + cmd.split() + ["--json", json.dumps(payload, ensure_ascii=False)]
    p = subprocess.run(args, capture_output=True, text=True)
    raw = p.stdout
    raw = raw[raw.find("{"):]
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw": p.stdout[:600], "_err": p.stderr[:600]}


def date_text(s):
    return (s or "").split(" ")[0]


def main():
    rows = json.load(open(ROWS, encoding="utf-8"))
    n = len(rows) + 1

    # 1. 新建工作表，插到第一位（已存在同名工作表则复用并清空，不重复建）
    g0 = call("sheet", "get", {"docid": DOCID})
    exists = [s for s in g0.get("sheets", []) if s.get("title") == NEW_SHEET]
    if exists:
        print("工作表已存在，复用并清空:", exists[0].get("sheet_id"))
        call("sheet", "ranges clear", {"docid": DOCID, "sheet": exists[0].get("sheet_id"),
                                       "range": f"A1:O{max(n + 20, 200)}", "confirm": True})
    else:
        rv = call("sheet", "subsheets add", {
            "docid": DOCID,
            "sheet": {"title": NEW_SHEET, "row_count": max(n + 20, 200), "column_count": len(COLUMNS)},
            "index": 1,
        })
        print("SUBSHEETS ADD:", rv.get("errcode"), rv.get("errmsg"), rv.get("error"))
        if rv.get("errcode") or rv.get("error"):
            print(json.dumps(rv, ensure_ascii=False)[:1000])
            raise SystemExit(1)

    # 2. 取新工作表的 sheet_id
    g = call("sheet", "get", {"docid": DOCID})
    sid = None
    for s in g.get("sheets", []):
        if s.get("title") == NEW_SHEET:
            sid = s.get("sheet_id")
    print("NEW SHEET ID:", sid, "| 工作表列表:", [(s.get("sheet_id"), s.get("title")) for s in g.get("sheets", [])])
    if not sid:
        raise SystemExit("新工作表没建出来")

    # 3. 组装二维数据（表头 + 数据行）
    header = [{"value": c, "style": {"bold": True, "bg_color": HEADER_BG, "vertical_align": "center",
                                     "horizontal_align": "center", "wrap": True}}
              for c in COLUMNS]
    body = []
    for r in rows:
        vals = []
        for c in COLUMNS:
            v = r.get(c, "")
            if c in ("进展日期", "开始时间", "完成时间"):
                v = date_text(v)
            if c == "事项序号":
                v = r.get(c)
            vals.append(v if v not in (None, "") else "")
        body.append(vals)

    # 4. 分块写入（15 列 → 每块 33 行 = 495 格 < 500）
    per = 500 // len(COLUMNS)
    chunks = [body[i:i + per] for i in range(0, len(body), per)]
    chunks.insert(0, [[c["value"] if isinstance(c, dict) else c for c in header]] + header)
    # 第一块：表头 + 前 N 行，单独处理表头样式
    first = [header] + chunks[1][:0]
    rest = chunks[1:]
    print("写入块数:", 1 + len(rest))

    rv = call("sheet", "cells batchset", {
        "docid": DOCID, "sheet": NEW_SHEET, "range": "A1", "cells": first, "verify": True})
    print("HEAD:", rv.get("errcode"), rv.get("errmsg"), "written=", rv.get("written_count"),
          (rv.get("verify_result") or {}).get("affected_range"))

    start_row = 2
    for i, ch in enumerate(rest):
        rng = f"A{start_row}"
        rv = call("sheet", "cells batchset", {
            "docid": DOCID, "sheet": NEW_SHEET, "range": rng, "cells": ch, "verify": True})
        print(f"CHUNK {i+1} @{rng}:", rv.get("errcode"), rv.get("errmsg"),
              "written=", rv.get("written_count"))
        if rv.get("errcode"):
            print(json.dumps(rv, ensure_ascii=False)[:800])
            break
        start_row += len(ch)

    # 5. 读回校验
    g2 = call("sheet", "get", {"docid": DOCID})
    for s in g2.get("sheets", []):
        print("工作表:", s.get("title"), "| 行", s.get("row_count"), "| 列", s.get("column_count"))
    print("DONE")


if __name__ == "__main__":
    main()
