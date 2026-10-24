#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在《集团人力近期重点工作进度表（甘特）》里新建子表「重点工作进度 v2」。

- 列顺序 = 字段添加顺序（API 无法改写列序），所以必须是新建子表，不能原地改
- 视图类型创建后不可改，所以视图一次建对：grid（按模块+性质分组）+ gantt（开始/完成时间）
- 旧子表「重点工作进度」不动，作为对照底稿
"""
import json, subprocess, sys, os

DOCID = "s3_AGUA63ivAJICNYb09k9UKSxyMYedn_a"
SHEET = "重点工作进度 v2"
HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = os.path.join(HERE, "rows_v2.json")

MODULES = ["人力资源规划", "招聘与配置", "培训与开发", "绩效管理", "薪酬福利", "员工关系", "待定位"]
NATURES = ["人", "流程", "成本", "其他"]
LEAD_TYPES = ["A", "B"]

FIELDS = [
    {"field_title": "事项序号", "field_type": "number",
     "property_number": {"decimal_places": 0, "use_separate": False}},
    {"field_title": "一级维度（六大模块）", "field_type": "single_select",
     "property_single_select": {"is_quick_add": False,
                                "options": [{"text": m, "style": i} for i, m in enumerate(MODULES)]}},
    {"field_title": "二级维度（人/流程/成本）", "field_type": "single_select",
     "property_single_select": {"is_quick_add": False,
                                "options": [{"text": n, "style": i} for i, n in enumerate(NATURES)]}},
    {"field_title": "具体事项", "field_type": "text"},
    {"field_title": "分项", "field_type": "text"},
    {"field_title": "分项内容简介", "field_type": "text"},
    {"field_title": "进展日期", "field_type": "date_time",
     "property_date_time": {"format": "yyyy-mm-dd", "auto_fill": False}},
    {"field_title": "进展内容", "field_type": "text"},
    {"field_title": "开始时间", "field_type": "date_time",
     "property_date_time": {"format": "yyyy-mm-dd", "auto_fill": False}},
    {"field_title": "完成时间", "field_type": "date_time",
     "property_date_time": {"format": "yyyy-mm-dd", "auto_fill": False}},
    {"field_title": "当日计划（周计划）", "field_type": "text"},
    {"field_title": "责任人", "field_type": "text"},
    {"field_title": "负责人", "field_type": "text"},
    {"field_title": "负责人类型", "field_type": "single_select",
     "property_single_select": {"is_quick_add": False,
                                "options": [{"text": t, "style": i} for i, t in enumerate(LEAD_TYPES)]}},
    {"field_title": "协调事项", "field_type": "text"},
]

WIDTHS = {
    "事项序号": 80, "一级维度（六大模块）": 130, "二级维度（人/流程/成本）": 110,
    "具体事项": 260, "分项": 180, "分项内容简介": 340,
    "进展日期": 110, "进展内容": 320, "开始时间": 110, "完成时间": 110,
    "当日计划（周计划）": 320, "责任人": 150, "负责人": 100,
    "负责人类型": 100, "协调事项": 180,
}


def call(cmd, payload):
    p = subprocess.run(["wecom-cli", "smartsheet"] + cmd.split() + ["--json", json.dumps(payload, ensure_ascii=False)],
                       capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"_raw": p.stdout[:800], "_err": p.stderr[:800]}


def main():
    rows = json.load(open(ROWS, encoding="utf-8"))

    # 0. 幂等：已存在同名子表就删掉重建（列顺序与数据都能整体换掉）
    ex = call("sheets list", {"docid": DOCID})
    for s0 in ex.get("sheets", []) or []:
        if s0.get("title") == SHEET:
            print("删除旧子表:", s0.get("sheet_id"))
            print(call("sheets delete", {"docid": DOCID, "sheet_id": s0.get("sheet_id"),
                                          "type": "delete"}))

    # 1. 新建子表（列顺序在这一次定死）
    #    注意：type=add 时后端要的是 sheet_title（新子表名），不是 new_sheet_title
    rv = call("sheets add", {"docid": DOCID, "type": "add", "sheet_title": SHEET, "fields": FIELDS})
    print("SHEETS ADD:", rv.get("errcode"), rv.get("errmsg"), rv.get("error"))
    if rv.get("errcode") or rv.get("error"):
        print(json.dumps(rv, ensure_ascii=False)[:1200])
        raise SystemExit(1)

    # 2. 取单选项 id
    fl = call("fields list", {"docid": DOCID, "sheet_title": SHEET, "limit": 100})
    opt = {}
    for f in fl.get("fields", []):
        t = f.get("field_title")
        prop = f.get("property") or f.get("property_single_select") or {}
        opts = (prop.get("single_select") or prop).get("options", []) if isinstance(prop, dict) else []
        if t in ("一级维度（六大模块）", "二级维度（人/流程/成本）", "负责人类型"):
            opt[t] = {o.get("text"): o.get("id") for o in (opts or [])}
    print("OPTS:", json.dumps(opt, ensure_ascii=False))

    def sel(field, text):
        oid = (opt.get(field) or {}).get(text)
        if not oid:
            return ""
        return [{"id": oid, "text": text}]

    # 3. 灌数据
    records = []
    for r in rows:
        records.append({"values": {
            "事项序号": r["事项序号"],
            "一级维度（六大模块）": sel("一级维度（六大模块）", r["一级维度（六大模块）"]),
            "二级维度（人/流程/成本）": sel("二级维度（人/流程/成本）", r["二级维度（人/流程/成本）"]),
            "具体事项": [{"text": r["具体事项"], "type": "text"}],
            "分项": [{"text": r["分项"], "type": "text"}],
            "分项内容简介": [{"text": r["分项内容简介"], "type": "text"}],
            "进展日期": r["进展日期"],
            "进展内容": [{"text": r["进展内容"], "type": "text"}],
            "开始时间": r["开始时间"],
            "完成时间": r["完成时间"],
            "当日计划（周计划）": [{"text": r["当日计划（周计划）"], "type": "text"}],
            "责任人": [{"text": r["责任人"], "type": "text"}],
            "负责人": [{"text": r["负责人"], "type": "text"}],
            "负责人类型": sel("负责人类型", r["负责人类型"]),
            "协调事项": [{"text": r["协调事项"], "type": "text"}],
        }})
    for i in range(0, len(records), 500):
        chunk = records[i:i + 500]
        rv2 = call("records add", {"docid": DOCID, "sheet_title": SHEET, "records": chunk})
        print("RECORDS ADD:", rv2.get("errcode"), rv2.get("errmsg"), "n=", len(rv2.get("records", []) or []))

    # 4. 视图：grid 分组 + gantt
    vs = call("views list", {"docid": DOCID, "sheet_title": SHEET, "limit": 100})
    grid_id = next((x["view_id"] for x in vs.get("views", []) or [] if x.get("view_type") == "grid"), None)
    print("GRID VIEW:", grid_id, [(v.get("view_title"), v.get("view_type")) for v in vs.get("views", []) or []])
    if grid_id:
        rv4 = call("views update", {"docid": DOCID, "sheet_title": SHEET, "type": "update",
                                    "views": [{"view_id": grid_id,
                                               "view_title": "进度总表（按模块分组）",
                                               "property": {
                                                   "group_spec": {"groups": [
                                                       {"field_title": "一级维度（六大模块）", "desc": False},
                                                       {"field_title": "二级维度（人/流程/成本）", "desc": False}]},
                                                   "frozen_field_count": 5},
                                               "col_infos": [{"field_title": k, "width": v} for k, v in WIDTHS.items()]}]})
        print("GRID UPDATE:", rv4.get("errcode"), rv4.get("errmsg"))

    rv3 = call("views add", {"docid": DOCID, "sheet_title": SHEET,
                             "views": [{"view_title": "甘特图", "view_type": "gantt",
                                        "property_gantt": {"start_date_field_title": "开始时间",
                                                           "end_date_field_title": "完成时间"}}]})
    print("GANTT:", rv3.get("errcode"), rv3.get("errmsg"),
          [(x.get("view_title"), x.get("view_type")) for x in rv3.get("views", []) or []])

    rv5 = call("views list", {"docid": DOCID, "sheet_title": SHEET, "limit": 100})
    print("FINAL VIEWS:", [(v.get("view_title"), v.get("view_type")) for v in rv5.get("views", []) or []])
    print("DONE")


if __name__ == "__main__":
    main()
