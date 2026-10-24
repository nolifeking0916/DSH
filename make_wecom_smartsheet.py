# -*- coding: utf-8 -*-
"""创建企业微信智能表格：制度征求意见收集表"""
import json, subprocess, sys

DOCS = [
    ("1",  "7-1",  "部门设置标准细则"),
    ("2",  "7-31", "员工作休细则"),
    ("3",  "9-0",  "招聘管理制度"),
    ("4",  "11-0", "绩效考核管理制度"),
    ("5",  "11-2", "绩效考核细则"),
    ("6",  "12-0", "薪酬管理制度"),
    ("7",  "36-0", "晋升管理制度"),
    ("8",  "36-1", "O序列员工晋升管理细则"),
    ("9",  "36-2", "P序列员工晋升管理细则"),
    ("10", "36-3", "M序列员工晋升管理细则"),
]

OPTS = [
    {"text": "无", "style": 7},
    {"text": "有疑问", "style": 20},
    {"text": "有建议", "style": 10},
    {"text": "疑问和建议都有", "style": 18},
]

def run(args):
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        print("EXIT", p.returncode, p.stderr[:800])
    return p.stdout.strip(), p.stderr.strip()

def call(*json_args):
    args = ["wecom-cli", "smartsheet"] + list(json_args[:1])
    out, err = run(args + ["--json", json.dumps(json_args[1], ensure_ascii=False)])
    return out, err

if __name__ == "__main__":
    fields = [{"field_title": "所属机构", "field_type": "text"}]
    for no, code, name in DOCS:
        fields.append({
            "field_title": "%s-1 %s（%s）是否有疑问和建议" % (no, name, code),
            "field_type": "single_select",
            "property_single_select": {"is_quick_add": False, "options": OPTS},
        })
        fields.append({
            "field_title": "%s-2 %s（%s）具体描述" % (no, name, code),
            "field_type": "text",
        })
    fields.append({"field_title": "提交人", "field_type": "created_user"})
    fields.append({"field_title": "提交时间", "field_type": "created_time",
                   "property_created_time": {"format": "yyyy-mm-dd hh:mm"}})

    payload = {"name": "制度（试行稿）征求意见收集表", "sheet_title": "反馈收集", "fields": fields}
    out, err = call("create", payload)
    print(out)
    print("ERR:", err)
