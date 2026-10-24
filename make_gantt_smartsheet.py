# -*- coding: utf-8 -*-
"""由《集团人力近期重点工作进度表》在线表格生成智能表格 + 甘特视图"""
import json, subprocess

TASKS = json.load(open("/tmp/tasks.json", encoding="utf-8"))
CAT_ORDER = ["奖金、补贴", "制度", "分析", "流程", "后台", "宣贯", "后续"]
CAT_STYLE = {"奖金、补贴": 19, "制度": 10, "分析": 16, "流程": 12, "后台": 24, "宣贯": 21, "后续": 7}

def call(cmd, payload):
    p = subprocess.run(["wecom-cli", "smartsheet"] + cmd.split() + ["--json", json.dumps(payload, ensure_ascii=False)],
                       capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"_raw": p.stdout[:800], "_err": p.stderr[:800]}

def d(s):
    return s.split(" ")[0]

fields = [
    {"field_title": "序号", "field_type": "number", "property_number": {"decimal_places": 0, "use_separate": False}},
    {"field_title": "一级分类", "field_type": "single_select",
     "property_single_select": {"is_quick_add": False,
                                "options": [{"text": c, "style": CAT_STYLE[c]} for c in CAT_ORDER]}},
    {"field_title": "分组", "field_type": "text"},
    {"field_title": "工作事项", "field_type": "text"},
    {"field_title": "概要", "field_type": "text"},
    {"field_title": "进展", "field_type": "text"},
    {"field_title": "周计划（1019-1025）", "field_type": "text"},
    {"field_title": "开始时间", "field_type": "date_time",
     "property_date_time": {"format": "yyyy-mm-dd", "auto_fill": False}},
    {"field_title": "完成时间", "field_type": "date_time",
     "property_date_time": {"format": "yyyy-mm-dd", "auto_fill": False}},
    {"field_title": "责任人", "field_type": "text"},
    {"field_title": "负责人", "field_type": "text"},
    {"field_title": "类型", "field_type": "single_select",
     "property_single_select": {"is_quick_add": False,
                                "options": [{"text": "A", "style": 18}, {"text": "B", "style": 10}]}},
    {"field_title": "协调事项", "field_type": "text"},
]

rv = call("create", {"name": "集团人力近期重点工作进度表（甘特）", "sheet_title": "重点工作进度", "fields": fields})
print("CREATE:", rv.get("errcode"), rv.get("errmsg"), rv.get("url"))
DOCID = rv.get("docid")
if not DOCID:
    raise SystemExit(rv)

# 取字段选项 id
fl = call("fields list", {"docid": DOCID, "sheet_title": "重点工作进度", "limit": 100})
opt = {"一级分类": {}, "类型": {}}
for f in fl.get("fields", []):
    t = f.get("field_title")
    if t in opt and isinstance(f.get("property"), dict):
        for o in (f["property"].get("single_select") or {}).get("options", []) or []:
            opt[t][o.get("text")] = o.get("id")
    if t in opt and isinstance(f.get("property_single_select"), dict):
        for o in f["property_single_select"].get("options", []) or []:
            opt[t][o.get("text")] = o.get("id")
print("OPTS:", opt)

records = []
for t in TASKS:
    vals = {
        "序号": t["seq"],
        "一级分类": [{"id": opt["一级分类"].get(t["cat"], ""), "text": t["cat"]}],
        "分组": t["group"],
        "工作事项": t["item"],
        "概要": t["summary"],
        "进展": t["progress"],
        "周计划（1019-1025）": t["week"],
        "开始时间": t["start"],
        "完成时间": t["end"],
        "责任人": t["owner"],
        "负责人": t["lead"],
        "类型": [{"id": opt["类型"].get(t["typ"], ""), "text": t["typ"]}],
        "协调事项": t["coord"],
    }
    records.append({"values": vals})

rv2 = call("records add", {"docid": DOCID, "sheet_title": "重点工作进度", "records": records})
print("RECORDS ADD:", rv2.get("errcode"), rv2.get("errmsg"), "n=", len(rv2.get("records", []) or []))

# 甘特视图
rv3 = call("views add", {"docid": DOCID, "sheet_title": "重点工作进度",
                         "views": [{"view_title": "甘特图", "view_type": "gantt",
                                    "property_gantt": {"start_date_field_title": "开始时间",
                                                       "end_date_field_title": "完成时间"}}]})
print("GANTT:", rv3.get("errcode"), rv3.get("errmsg"),
      [(x.get("view_title"), x.get("view_type")) for x in rv3.get("views", []) or []])

# 列表视图：按一级分类分组 + 列宽
vs = call("views list", {"docid": DOCID, "sheet_title": "重点工作进度", "limit": 100})
grid_id = next((x["view_id"] for x in vs.get("views", []) if x.get("view_type") == "grid"), None)
widths = {"序号": 70, "一级分类": 120, "分组": 240, "工作事项": 280, "概要": 320, "进展": 400,
          "周计划（1019-1025）": 400, "开始时间": 120, "完成时间": 120, "责任人": 160, "负责人": 120,
          "类型": 80, "协调事项": 200}
if grid_id:
    rv4 = call("views update", {"docid": DOCID, "sheet_title": "重点工作进度", "type": "update",
                                "views": [{"view_id": grid_id,
                                           "property": {"group_spec": {"groups": [{"field_title": "一级分类", "desc": False}]},
                                                        "frozen_field_count": 1},
                                           "col_infos": [{"field_title": k, "width": v} for k, v in widths.items()]}]})
    print("GRID UPDATE:", rv4.get("errcode"), rv4.get("errmsg"))

json.dump({"docid": DOCID, "url": rv.get("url")}, open("/tmp/gantt_doc.json", "w", encoding="utf-8"), ensure_ascii=False)
print("DONE", DOCID)
