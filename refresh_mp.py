# -*- coding: utf-8 -*-
"""按系统后台最新职位重刷 MP 名单：删 13 人 + 匹配最新岗位/职级 + 入职日期"""
import csv, sys, json, collections

sys.path.insert(0, "/Users/leto/WorkBuddy/HR技术中台/scripts")
import hrq

REMOVE = {"史芳芳", "王庸", "周清华", "董猛", "何翔", "敖慧丹", "王明明", "朱晁均", "蒋成", "赵雯婷", "李岳", "宋真", "周京"}
ORG_DB = {
    "云上度假村": ["松鼠酒店"],
    "云上景区": ["云上景区"],
    "浙江营销": ["浙江营销"],
    "集团部门": ["集团部门"],
    "大竹海": ["中国大竹海"],
    "茅山森林世界": ["茅森景区", "茅森酒店"],
    "研创院": ["研创院"],
    "工程管理分公司": ["工程管理分公司"],
    "余村演艺分公司": ["云上余村"],
    "星空酒店": ["星空酒店"],
    "聚力旅行社": ["聚力旅行社"],
    "恐龙酒店": ["恐龙酒店"],
    "云上商管": ["云上商管"],
    "熊猫部落": ["熊猫部落"],
    "控股集团": ["控股集团"],
}

rows = list(csv.reader(open("/tmp/mp.csv", encoding="utf-8")))
src = []
for r in rows[1:]:
    if not r or not r[0].strip() or r[0].strip() == "机构":
        continue
    co = r[0].strip().replace("\n", "")
    if co == "云上草原景区":
        co = "云上景区"
    name = r[5].strip()
    if name in REMOVE:
        continue
    src.append({"co": co, "pos": r[3].strip(), "lv": r[4].strip(), "name": name,
                "note": r[6].strip() if len(r) > 6 else ""})
print("剩余名单:", len(src))

names = sorted({x["name"] for x in src})
IN = ",".join("'" + n.replace("'", "''") + "'" for n in names)
sql = ('SELECT "trueName","companyShortName","positionName","levelName","entryDate","stateName","leaveDate" '
       'FROM hr_persons_all WHERE "trueName" IN (%s)' % IN)
cols, data = hrq.execute_sql(sql)
print("DB 命中行:", len(data), "通道:", hrq.LAST_CHANNEL)

idx = collections.defaultdict(list)
for row in data:
    d = dict(zip(cols, row))
    idx[d["trueName"]].append(d)

SERIES = {"管理": "M", "专业": "P", "技术": "P", "操作": "O"}
CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

def short_lv(raw):
    raw = (raw or "").strip()
    for k, v in SERIES.items():
        if raw.startswith(k):
            n = CN.get(raw[len(k):len(k) + 1], "")
            return "%s%s" % (v, n) if n else raw
    return raw

def pick(name, co):
    cands = idx.get(name, [])
    if not cands:
        return None, ""
    want = ORG_DB.get(co, [co])
    for d in cands:
        if d["stateName"] == "在职" and d["companyShortName"] in want:
            return d, ""
    acts = [d for d in cands if d["stateName"] == "在职"]
    if len(acts) == 1:
        return acts[0], "后台机构:%s" % acts[0]["companyShortName"]
    if acts:
        d = acts[0]
        return d, "后台机构:%s，同名人多需核对" % d["companyShortName"]
    return None, ""

out, nohit, left = [], [], []
for x in src:
    d, tag = pick(x["name"], x["co"])
    if not d:
        nohit.append("%s(%s)" % (x["name"], x["co"]))
        out.append({**x, "entry": "", "note2": "系统后台无记录"})
        continue
    entry = (d["entryDate"] or "")[:10]
    note = x["note"]
    tags = []
    if tag:
        tags.append(tag)
    if d["stateName"] != "在职":
        tags.append("系统后台显示离职")
        left.append(x["name"])
    note2 = "；".join(tags)
    same_org = not tag.startswith("后台机构")
    out.append({"co": x["co"], "name": x["name"],
                "pos": ((d["positionName"] or x["pos"]).strip() if same_org else x["pos"]),
                "lv": ((short_lv(d["levelName"]) or x["lv"]) if same_org else x["lv"]),
                "entry": entry, "note": note, "note2": note2})

with open("/tmp/mp_final.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["co", "pos", "lv", "name", "entry", "note", "note2"])
    for x in out:
        w.writerow([x["co"], x["pos"], x["lv"], x["name"], x["entry"], x["note"], x["note2"]])

by = collections.Counter(x["co"] for x in out)
print("机构:", len(by), dict(by))
print("M/P:", sum(1 for x in out if x["lv"].startswith("M")), sum(1 for x in out if x["lv"].startswith("P")))
print("无记录:", nohit)
print("显示离职:", left)
print("岗位有变化:", sum(1 for a, b in zip(src, out) if a["pos"] != b["pos"]))
print("职级有变化:", sum(1 for a, b in zip(src, out) if a["lv"] != b["lv"]))
