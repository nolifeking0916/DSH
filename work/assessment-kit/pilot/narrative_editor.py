#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判读话术库的小后台（命令行）。

话术规则存在**云上数据库** public.report_narrative。本脚本负责：
  list                 列出全部规则（从云端拉）
  show <维度> <档位>    看某一条规则
  set <维度> <档位> <极> --text "新话术" [--title "标题"]
                       改一条 ⇒ 打印一段 UPSERT SQL，拿去云开发控制台执行即生效
  export               导出整库为本地 JSON 快照（离线兜底用）

为什么不做成「直接写库」：本机连不上 PG（实例是 SHARED 租户），
写操作要走有 service_role 权限的通道 ⇒ 这里给出 SQL，由控制台或管理台执行。

用法：
    python3 pilot/narrative_editor.py list
    python3 pilot/narrative_editor.py set regu 优秀 __any__ --text "新的判读话术"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENDPOINT = os.environ.get(
    "ASSESSMENT_API",
    "https://uu-one-d4gc4ot78a702cb70-1257197409.ap-shanghai.app.tcloudbase.com/api/assessment",
)
SNAPSHOT = os.path.join(ROOT, "data", "narrative_rules.json")


def fetch():
    req = urllib.request.Request(ENDPOINT + "?action=rules", headers={"User-Agent": "narrative-editor"})
    j = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore"))
    return j.get("rules") or []


def q(s):
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def upsert_sql(rules):
    lines = []
    for r in rules:
        lines.append("(%s,%s,%s,%s,%s,%s,%s,%s,0,TRUE)" % (
            q(r.get("module")), q(r.get("dimension")), q(r.get("band")),
            q(r.get("pole") or "__any__"), q(r.get("pole_label") or ""),
            q(r.get("kind")), q(r.get("title")), q(r.get("text"))))
    return ("INSERT INTO public.report_narrative "
            "(module,dimension,band,pole,pole_label,kind,title,text,sort,active) VALUES\n"
            + ",\n".join(lines) +
            "\nON CONFLICT (module,dimension,band,pole,kind) DO UPDATE SET "
            "pole_label=EXCLUDED.pole_label,title=EXCLUDED.title,text=EXCLUDED.text,"
            "active=TRUE,updated_at=now();")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["list", "show", "set", "export"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--text", default=None)
    ap.add_argument("--title", default=None)
    a = ap.parse_args()

    rules = fetch()
    if a.action == "list":
        for r in rules:
            print("%-10s %-8s %-6s %-6s %-10s %s" % (
                r.get("module"), r.get("dimension"), r.get("band"),
                r.get("pole"), r.get("kind"), (r.get("title") or "")))
        print("\n共 %d 条" % len(rules))
        return 0

    if a.action == "export":
        out = {"meta": {"version": "20261025", "bands": ["顶尖", "优秀", "良好", "合格", "待提升"],
                        "note": "从云端 report_narrative 导出的快照（离线兜底用）"},
               "rules": rules}
        json.dump(out, open(SNAPSHOT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("已导出 → %s（%d 条）" % (SNAPSHOT, len(rules)))
        return 0

    dim, band = (a.args + [None, None])[:2]
    hit = None
    for r in rules:
        if r.get("dimension") == dim and r.get("band") == band:
            if len(a.args) < 3 or r.get("pole") == a.args[2]:
                hit = r
                break
    if hit is None:
        print("没找到这条规则：%s / %s" % (dim, band))
        return 2

    if a.action == "show":
        print("%s / %s / %s / %s" % (hit.get("module"), hit.get("dimension"),
                                     hit.get("band"), hit.get("pole")))
        print("标题：%s" % (hit.get("title") or ""))
        print("话术：%s" % (hit.get("text") or ""))
        return 0

    if a.text:
        hit["text"] = a.text
    if a.title:
        hit["title"] = a.title
    print("-- 在控制台执行下面这段即生效 --")
    print(upsert_sql([hit]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
