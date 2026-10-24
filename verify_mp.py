# -*- coding: utf-8 -*-
"""实时核对：MP 名单 142 人 ↔ 企业后台（hr_persons_all）最新岗位"""
import csv, sys, collections, datetime

sys.path.insert(0, "/Users/leto/WorkBuddy/HR技术中台/scripts")
import hrq

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
SERIES = {"管理": "M", "专业": "P", "技术": "P", "操作": "O"}
CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

def short_lv(raw):
    raw = (raw or "").strip()
    for k, v in SERIES.items():
        if raw.startswith(k):
            n = CN.get(raw[len(k):len(k) + 1], "")
            return "%s%s" % (v, n) if n else raw
    return raw

src = list(csv.DictReader(open("/tmp/mp_keep.csv", encoding="utf-8")))
names = sorted({x["name"] for x in src})
IN = ",".join("'" + n.replace("'", "''") + "'" for n in names)
sql = ('SELECT "trueName","companyShortName","unitName","positionName","levelName",'
       '"entryDate","stateName","leaveDate","number" FROM hr_persons_all WHERE "trueName" IN (%s)' % IN)
cols, rows = hrq.execute_sql(sql)
print("拉取时间:", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "｜ 通道:", hrq.LAST_CHANNEL, "｜ 命中:", len(rows), "行")

idx = collections.defaultdict(list)
for r in rows:
    d = dict(zip(cols, r))
    idx[d["trueName"]].append(d)

out, stats = [], collections.Counter()
for x in src:
    co, name = x["co"], x["name"]
    want = ORG_DB.get(co, [co])
    cand = idx.get(name, [])
    same = [d for d in cand if d["stateName"] == "在职" and d["companyShortName"] in want]
    other = [d for d in cand if d not in same]
    rec = {"co": co, "name": name, "list_pos": x["pos"], "list_lv": x["lv"],
           "db_org": "", "db_unit": "", "db_pos": "", "db_lv": "", "db_entry": "",
           "db_state": "", "db_number": "", "status": "", "alt": ""}
    rec["alt"] = "；".join("%s/%s/%s/%s" % (d["companyShortName"], d["positionName"], d["stateName"], (d["entryDate"] or "")[:10])
                           for d in other if d["stateName"] == "在职")[:200]
    if len(same) == 1:
        d = same[0]
        rec.update(db_org=d["companyShortName"], db_unit=d["unitName"] or "", db_pos=(d["positionName"] or "").strip(),
                   db_lv=short_lv(d["levelName"]), db_entry=(d["entryDate"] or "")[:10],
                   db_state=d["stateName"], db_number=str(d["number"] or ""))
        if rec["db_pos"] == rec["list_pos"]:
            rec["status"] = "一致"
        else:
            rec["status"] = "岗位更新"
    elif len(same) > 1:
        rec["status"] = "同名多人待核"
    else:
        leavers = [d for d in cand if d["stateName"] != "在职"]
        rec["status"] = "无本机构在职记录"
        if leavers:
            d = leavers[0]
            rec.update(db_org=d["companyShortName"], db_pos=(d["positionName"] or "").strip(),
                       db_lv=short_lv(d["levelName"]), db_entry=(d["entryDate"] or "")[:10],
                       db_state="离职", db_number=str(d["number"] or ""))
    stats[rec["status"]] += 1
    out.append(rec)

with open("/tmp/mp_verify.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader(); w.writerows(out)

# 最终采用值：同机构入库的用后台；其余保留名单并标注
final = []
for rec in out:
    ok = rec["status"] in ("一致", "岗位更新")
    if rec["status"] == "岗位更新":
        note = ["岗位按后台更新，名单原值：%s" % rec["list_pos"]]
    elif ok:
        note = []
    if ok and rec["db_lv"] and rec["db_lv"] != rec["list_lv"]:
        note.append("职级按后台更新（名单原值：%s）" % rec["list_lv"])
    else:
        note = [rec["status"] + ("；后台在职同名记录：%s" % rec["alt"] if rec["alt"] else "；后台无同名记录")]
    final.append({"co": rec["co"], "name": rec["name"],
                  "pos": rec["db_pos"] if ok else rec["list_pos"],
                  "lv": rec["db_lv"] if ok else rec["list_lv"],
                  "entry": rec["db_entry"] if ok else "",
                  "note": "", "note2": "；".join([n for n in note if n])})
with open("/tmp/mp_final.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["co", "pos", "lv", "name", "entry", "note", "note2"])
    w.writeheader(); w.writerows(final)

print("核对结果:", dict(stats))
print("\n需人工确认：")
for rec in out:
    if rec["status"] not in ("一致", "岗位更新"):
        print(" %-14s %-8s 名单:%s(%s) | 后台:%s %s %s | 候选:%s"
              % (rec["co"], rec["name"], rec["list_pos"], rec["list_lv"],
                 rec["db_org"] or "-", rec["db_pos"] or "-", rec["db_state"] or "-", rec["alt"] or "-"))
print("\n岗位更新示例：")
n = 0
for rec in out:
    if rec["status"] == "岗位更新" and n < 8:
        print(" %-14s %-6s %s → %s" % (rec["co"], rec["name"], rec["list_pos"], rec["db_pos"])); n += 1
