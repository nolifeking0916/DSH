#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "review-inbox" / "metadata-enrichment-20261110"
BASELINE = OUT / "before-hashes.json"
CATALOG = ROOT / "scripts" / "metadata-catalog.json"
ROOTS = ("docs", "assets", "outputs", "openspec", "migration")
NATIVE = {"README.md", "AGENTS.md", "docs/README.md", "outputs/管理原话-20261110/00-阅读入口.md"}
TITLES = {
 "": "HR 知识仓", "docs": "文档中心", "docs/current": "当前阅读",
 "docs/current/final": "定稿文件", "docs/current/employee": "员工版制度",
 "docs/current/ppt": "汇报与演示语义", "docs/evidence": "证据与回执（已收起）",
 "docs/evidence/final": "定稿校验留痕", "docs/evidence/employee": "员工版校验留痕",
 "docs/evidence/ppt": "演示校验留痕", "docs/evidence/nested": "嵌套留档证据",
 "docs/working": "工作稿（已收起）", "docs/working/revision": "修订工作稿",
 "docs/working/revision-v5": "第五版修订工作稿", "docs/working/research": "调研材料",
 "docs/working/meeting-templates": "会议模板工作稿", "docs/extracted": "语义抽取副本（已收起）",
 "docs/extracted/templates": "模板语义副本", "docs/extracted/meeting-templates": "会议模板语义副本",
 "docs/reference": "参考资料", "docs/reference/regulation": "法规与依据",
 "docs/runbooks": "运行手册", "assets": "原始附件（私有 Git）",
 "assets/current": "当前附件", "assets/reference": "参考附件", "assets/working": "工作附件",
 "assets/evidence": "证据附件", "outputs": "定稿产出（私有 Git）",
 "outputs/旧件留档": "旧件留档（已收起）", "outputs/管理原话-20261110": "管理原话（限内部）",
 "openspec": "OpenSpec 规格", "migration": "迁移台账（已收起）",
}
DOMAINS = [
 ("管理原话", ("管理原话", "管理专题", "孙晓东")),
 ("职代会", ("职代", "职工代表", "代表选举", "职工总数", "附件五", "附件六", "选区", "报备")),
 ("干部管理", ("干部", "胜任力", "继任", "任期", "考察", "测评", "访谈")),
 ("薪酬绩效", ("薪酬", "工资", "薪级", "绩效", "津贴", "奖惩")),
 ("招聘配置", ("招聘", "人才吸引", "入职", "引荐", "面试", "试用期")),
 ("员工关系", ("离职", "员工关系", "劳动合同", "女职工", "请假", "考勤")),
 ("文件归档", ("归档", "档案")), ("会议管理", ("会议", "议题", "纪要")),
 ("数据治理", ("数据", "口径", "指标", "名册", "通讯录", "机构总览")),
 ("系统运维", ("同步", "运行", "openknowledge", "openviking", "openspec", "脚本", "技术")),
 ("阅读导航", ("readme", "入口", "导航", "agents")),
 ("企业文化", ("荐读", "海报", "语录", "认知上行")),
]

def digest(path, body=False):
    if body and path.suffix.lower() in {".md", ".markdown"}:
        return hashlib.sha256(split_body(path.read_text(encoding="utf-8")).encode()).hexdigest()
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()

def legacy_body_digest(path):
    if path.suffix.lower() not in {".md", ".markdown"}: return digest(path)
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0: return hashlib.sha256(text[end + 5:].encode()).hexdigest()
    return hashlib.sha256(text.encode()).hexdigest()

def split_body(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            body = text[end + 5:]
            # The API inserts one blank separator after frontmatter; it is not document prose.
            return body[1:] if body.startswith("\n") else body
    return text

def frontmatter(text):
    result = {}
    if not text.startswith("---\n"): return result
    end = text.find("\n---\n", 4)
    if end < 0: return result
    for line in text[4:end].splitlines():
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if match:
            value = match.group(2).strip()
            result[match.group(1)] = "[block]" if match.group(1) == "tags" and not value else value
    return result

def clean(text):
    text = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    return re.sub(r"\s+", " ", re.sub(r"[<>*_#|\x60]", "", text)).strip()

def title_description(path, category, life):
    title, description = path.stem, ""
    if path.suffix.lower() in {".md", ".markdown", ".txt"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = frontmatter(text)
        if fm.get("title"): title = fm["title"].strip("\"'")
        body = split_body(text)
        heading = re.search(r"(?m)^#\s+(.+?)\s*$", body)
        if heading and not fm.get("title"): title = clean(heading.group(1))
        if fm.get("description"): description = fm["description"].strip("\"'")
        if not description:
            for block in re.split(r"\n\s*\n", body):
                raw = block.strip()
                if raw.startswith("#"): continue
                candidate = clean(raw)
                if not candidate or candidate.startswith(("---", "source_", "sha256", "更新时间", "版本：", "- ", "1.", "2.", "3.")): continue
                description = candidate[:180] + ("…" if len(candidate) > 180 else "")
                break
    return title[:160], description or f"{category}资料，{life}；依据文件名、所在目录和可读取文本归类。"

def domain(rel):
    if rel.startswith("docs/runbooks/"): return "系统运维"
    for label, needles in DOMAINS:
        if any(n.lower() in rel.lower() for n in needles): return label
    return "人力资源"

def kind(path, rel):
    low, ext = rel.lower(), path.suffix.lower()
    if any(x in low for x in ("模板", "template", "登记表", "报告单", "审议情况")): return "表单模板"
    if any(x in low for x in ("校验", "回执", "receipt", "provenance", "verification", "manifest")): return "校验留痕"
    if rel.startswith("openspec/"): return "规格说明"
    if rel.startswith("docs/runbooks/") or any(x in low for x in ("手册", "指南")): return "运行手册"
    if any(x in low for x in ("细则", "办法", "制度", "规程", "规范", "通知")): return "制度通知"
    if ext in {".xlsx", ".xls", ".csv"}: return "表格数据"
    if ext in {".pptx", ".ppt"}: return "演示材料"
    if ext in {".png", ".jpg", ".jpeg", ".svg", ".webp"}: return "图片海报"
    if any(x in low for x in ("报告", "汇报", "总结", "清单")): return "报告清单"
    if ext in {".docx", ".doc", ".pdf"}: return "办公原件"
    return "文本资料" if ext in {".md", ".markdown", ".txt"} else "其他资料"

def life(rel, doc_kind):
    low = rel.lower()
    if any(x in low for x in ("旧件", "留档", "backup", "未整合", "/v1", "/v2", "/v3", "/v4", "/v5")): return "历史留档"
    if rel.startswith("docs/evidence/") or rel.startswith("migration/") or doc_kind == "校验留痕": return "证据留痕"
    if rel.startswith("docs/working/"): return "工作草稿"
    if rel.startswith("docs/extracted/"): return "语义副本"
    if rel.startswith("openspec/"): return "规格管理"
    if doc_kind == "表单模板": return "模板工具"
    if rel.startswith("docs/runbooks/") or rel in {"README.md", "AGENTS.md", "docs/README.md"}: return "使用指引"
    if rel.startswith("docs/current/"): return "当前阅读"
    if rel.startswith("outputs/管理原话-"): return "限内阅读"
    if rel.startswith("outputs/") or ".final." in low: return "定稿产出"
    return "资料归档"

def scope(rel): return "私有Git" if rel.startswith(("assets/", "outputs/")) else "OpenViking"
def native(rel): return rel in NATIVE or rel.startswith("docs/runbooks/")

def files():
    result = [ROOT / "README.md", ROOT / "AGENTS.md"]
    for name in ROOTS:
        base = ROOT / name
        if base.exists(): result += [p for p in base.rglob("*") if p.is_file() and ".ok" not in p.relative_to(ROOT).parts]
    return sorted(set(result), key=lambda p: p.relative_to(ROOT).as_posix())

def record(path):
    rel = path.relative_to(ROOT).as_posix()
    category, doc_kind = domain(rel), kind(path, rel)
    status, retrieval = life(rel, doc_kind), scope(rel)
    title, description = title_description(path, category, status)
    ext = path.suffix.lower().lstrip(".") or "无扩展名"
    tags = [f"主题-{category}", f"类型-{doc_kind}", f"状态-{status}", f"检索-{retrieval}", f"格式-{ext.upper()}"]
    match = re.search(r"(20\d{2})[-年]?(\d{2})", rel)
    month = f"{match.group(1)}-{match.group(2)}" if match else None
    if month: tags.append(f"日期标记-{month}")
    return {"path": rel, "title": title, "description": description, "tags": tags,
     "category": category, "document_type": doc_kind, "lifecycle": status, "search_scope": retrieval,
     "format": ext, "document_month": month, "size_bytes": path.stat().st_size,
     "sha256": digest(path), "body_sha256": digest(path, True),
     "metadata_surface": "openknowledge_frontmatter" if native(rel) else "catalog_only_preserve_original"}

def folders(file_list):
    result = {""}
    for path in file_list:
        parts = path.relative_to(ROOT).parts[:-1]
        for i in range(1, len(parts) + 1):
            value = Path(*parts[:i]).as_posix()
            if value.startswith(ROOTS) and ".ok" not in parts[:i]: result.add(value)
    return sorted(result, key=lambda x: (x.count("/"), x))

def folder_meta(folder, records):
    prefix = folder + "/" if folder else ""
    descendants = [r for r in records if not prefix or r["path"].startswith(prefix)]
    primary = Counter(r["category"] for r in descendants).most_common(1)[0][0] if descendants else "人力资源"
    status, retrieval = (life(prefix, ""), scope(prefix)) if folder else ("使用指引", "OpenViking")
    tags = sorted({t for r in descendants for t in r["tags"] if not t.startswith(("格式-", "日期标记-"))})[:12]
    for tag in (f"主题-{primary}", f"状态-{status}", f"检索-{retrieval}"):
        if tag not in tags: tags.append(tag)
    return {"title": TITLES.get(folder, Path(folder).name if folder else "HR 知识仓"),
     "description": f"收录 {len(descendants)} 个文件，以{primary}相关内容为主；目录标签由文件路径、格式和可读取文本汇总生成。",
     "tags": tags, "category": primary, "lifecycle": status, "search_scope": retrieval, "file_count": len(descendants)}

def server():
    proc = subprocess.run(["ok", "status", "--json"], cwd=ROOT, text=True, capture_output=True, timeout=30)
    status = json.loads(proc.stdout) if proc.returncode == 0 else {}
    if not status.get("server", {}).get("alive"): raise RuntimeError("OpenKnowledge server unavailable")
    return f"http://127.0.0.1:{status['server']['port']}"

def request(base, method, path, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as response: return json.load(response)

def apply_folder(base, folder, expected):
    encoded = urllib.parse.quote(folder)
    current = request(base, "GET", "/api/folder-config?path=" + encoded).get("frontmatter_local") or {}
    patch = {}
    for key, value in expected.items():
        if key == "tags":
            old = current.get(key) if isinstance(current.get(key), list) else []
            merged = list(dict.fromkeys(old + value))
            if merged != old: patch[key] = merged
        elif current.get(key) in (None, "", []): patch[key] = value
    if folder == "docs/runbooks" and current.get("category") == "人力资源":
        patch["category"] = expected["category"]
        patch["description"] = expected["description"]
        old_tags = current.get("tags") if isinstance(current.get("tags"), list) else []
        patch["tags"] = list(dict.fromkeys([t for t in old_tags if t != "主题-人力资源"] + expected["tags"]))
    if patch: request(base, "PUT", "/api/folder-config", {"path": folder, "frontmatter": patch})
    actual = request(base, "GET", "/api/folder-config?path=" + encoded).get("frontmatter_local") or {}
    for key, value in expected.items():
        if key == "tags":
            if not set(value).issubset(set(actual.get(key) or [])): raise RuntimeError("folder tags readback: " + folder)
        elif actual.get(key) != value: raise RuntimeError(f"folder {key} readback: {folder}")
    return bool(patch)

def apply_native(base, item):
    rel, path = item["path"], ROOT / item["path"]
    before = path.read_text(encoding="utf-8")
    old = frontmatter(before)
    expected = {"title": item["title"], "description": item["description"], "tags": item["tags"],
     "category": item["category"], "document_type": item["document_type"], "lifecycle": item["lifecycle"],
     "search_scope": item["search_scope"], "type": "note"}
    patch = {k: v for k, v in expected.items() if not old.get(k)}
    if rel.startswith("docs/runbooks/") and old.get("category") != expected["category"]:
        patch["category"] = expected["category"]
        patch["tags"] = expected["tags"]
    if old.get("description") and old.get("description") == old.get("title") and expected["description"] != old["description"]:
        patch["description"] = expected["description"]
    if patch:
        request(base, "POST", "/api/frontmatter-patch", {"docName": rel.rsplit(".", 1)[0], "patch": patch,
         "summary": "补全知识文档属性与分类标签", "agentId": "hr-metadata-enricher", "agentName": "HR 元数据补全", "clientName": "dsh"})
    after = path.read_text(encoding="utf-8")
    if split_body(after) != split_body(before): raise RuntimeError("document body changed: " + rel)
    actual = frontmatter(after)
    for key in patch:
        if key == "tags":
            if "tags:" not in after: raise RuntimeError("document tags readback: " + rel)
        elif key not in actual: raise RuntimeError(f"document {key} readback: {rel}")
    return bool(patch)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.apply and not args.check: parser.error("choose --apply or --check")
    file_list = files()
    records = [record(p) for p in file_list]
    folder_list = folders(file_list)
    if args.apply:
        OUT.mkdir(parents=True, exist_ok=True)
        if not BASELINE.exists():
            before = {p.relative_to(ROOT).as_posix(): {"sha256": digest(p), "body_sha256": digest(p, True)} for p in file_list}
            BASELINE.write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")
        base = server()
        folder_updates = sum(apply_folder(base, f, folder_meta(f, records)) for f in folder_list)
        native_updates = sum(apply_native(base, r) for r in records if native(r["path"]))
        records = [record(p) for p in file_list]
        catalog = {"version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
         "rules": "路径 + 文件格式 + 可读取文本；不推断人员身份、制度效力或业务裁定",
         "file_count": len(records), "folder_count": len(folder_list),
         "native_frontmatter_count": sum(native(r["path"]) for r in records),
         "catalog_only_count": sum(not native(r["path"]) for r in records),
         "folders": {f: folder_meta(f, records) for f in folder_list}, "files": records}
        CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = {"status": "pass", "files": len(records), "folders": len(folder_list),
         "folder_updates": folder_updates, "native_document_updates": native_updates}
        (OUT / "apply-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return
    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    errors = []
    for item in records:
        rel, before = item["path"], baseline.get(item["path"])
        if before and native(rel) and before["body_sha256"] not in {item["body_sha256"], legacy_body_digest(ROOT / rel)}:
            errors.append("native_body_changed:" + rel)
        if before and not native(rel) and item["sha256"] != before["sha256"]: errors.append("original_changed:" + rel)
        for key in ("title", "description", "tags", "category", "document_type", "lifecycle", "search_scope"):
            if not item.get(key): errors.append(f"missing_{key}:" + rel)
        if native(rel):
            fm = frontmatter((ROOT / rel).read_text(encoding="utf-8"))
            for key in ("title", "description", "tags", "category", "document_type", "lifecycle", "search_scope", "type"):
                if key not in fm: errors.append(f"native_frontmatter_{key}:" + rel)
    for folder in folder_list:
        if not (ROOT / folder / ".ok" / "frontmatter.yml").is_file(): errors.append("folder_frontmatter_missing:" + (folder or "."))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else {}
    if catalog.get("file_count") != len(records): errors.append("catalog_file_count")
    if catalog.get("folder_count") != len(folder_list): errors.append("catalog_folder_count")
    report = {"status": "pass" if not errors else "fail", "file_count": len(records), "folder_count": len(folder_list),
     "native_frontmatter_count": sum(native(r["path"]) for r in records), "catalog_only_count": sum(not native(r["path"]) for r in records),
     "baseline_file_count": len(baseline), "errors": errors}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if errors: raise SystemExit(1)

if __name__ == "__main__": main()
