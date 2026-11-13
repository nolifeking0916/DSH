#!/usr/bin/env python3
"""DSH-owned, read-only whole-machine AI-output discovery ledger."""
from __future__ import annotations
import argparse, fcntl, hashlib, json, os, re, sqlite3, sys, uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "scripts" / "output_ledger_sources.json"
STATE = Path.home() / "Library" / "Application Support" / "hr-knowledge-sync"
DB_PATH = STATE / "output-ledger.sqlite3"
RAW_REPORT = STATE / "output-ledger-report.json"
SUMMARY = ROOT / "outputs" / "产出总账" / "README.md"
PENDING = ROOT / "outputs" / "产出总账" / "待确认清单.md"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
TEXT_EXTS = {".md", ".markdown", ".txt"}
OFFICE_EXTS = {".docx", ".pptx", ".xlsx", ".pdf"}
PERSONAL_PATH = re.compile(r"(?:^|/)(?:人员|人事|员工|薪酬|工资|薪级|工号|测评|个人结果|离职|通讯录|花名册)(?:/|[-_])", re.I)
SECRET_PATH = re.compile(r"(?:^|/)(?:\.env|secrets?|credentials?|tokens?|keys?)(?:$|/|\.)", re.I)
FINAL_MARK = re.compile(r"(?:\.final\.|\.receipt\.|\.provenance\.|final|定稿|回执|收据|校验报告|覆盖与校验)", re.I)

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def contained(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute path and parent traversal are forbidden")
    base = root.resolve()
    result = (base / path).resolve()
    if result != base and base not in result.parents:
        raise ValueError("path escapes declared root")
    return result

def load_config(path=CONFIG_PATH):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("version") != 1 or not isinstance(value.get("scan_roots"), list):
        raise ValueError("invalid output ledger config")
    return value

def init_db(path=DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS artifacts(
      artifact_id TEXT PRIMARY KEY, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
      origin_confidence TEXT NOT NULL, origin_reason TEXT NOT NULL,
      current_status TEXT NOT NULL, current_sha256 TEXT, current_path TEXT
    );
    CREATE TABLE IF NOT EXISTS locations(
      location_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
      path TEXT NOT NULL, device INTEGER, inode INTEGER, first_seen TEXT NOT NULL,
      last_seen TEXT NOT NULL, present INTEGER NOT NULL DEFAULT 1,
      relation TEXT NOT NULL DEFAULT 'origin', UNIQUE(path)
    );
    CREATE INDEX IF NOT EXISTS idx_locations_identity ON locations(device,inode);
    CREATE TABLE IF NOT EXISTS versions(
      version_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
      sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
      first_seen TEXT NOT NULL, last_seen TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_versions_hash ON versions(sha256);
    CREATE TABLE IF NOT EXISTS observations(
      observation_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
      path TEXT NOT NULL, observed_at TEXT NOT NULL, status TEXT NOT NULL,
      reasons_json TEXT NOT NULL, sha256 TEXT, size_bytes INTEGER NOT NULL,
      mtime_ns INTEGER NOT NULL, device INTEGER, inode INTEGER,
      origin_confidence TEXT NOT NULL, origin_reason TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_observations_path_time ON observations(path,observed_at);
    CREATE TABLE IF NOT EXISTS file_cache(
      path TEXT PRIMARY KEY, device INTEGER NOT NULL, inode INTEGER NOT NULL,
      size_bytes INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, sha256 TEXT NOT NULL
    );
    """)
    return db

def is_excluded(path, config):
    resolved = path.resolve()
    for item in config.get("excluded_roots", []):
        base = Path(item).resolve()
        if resolved == base or base in resolved.parents:
            return True
    return False

def walk_candidates(config):
    allowed = set(config["allowed_extensions"])
    excluded_names = set(config.get("excluded_dir_names", []))
    seen_roots = set()
    for raw_root in config["scan_roots"]:
        root = Path(raw_root)
        if not root.is_dir():
            continue
        resolved_root = root.resolve()
        if resolved_root in seen_roots or is_excluded(resolved_root, config):
            continue
        seen_roots.add(resolved_root)
        for base, dirs, files in os.walk(root, followlinks=False):
            base_path = Path(base)
            kept = []
            for name in dirs:
                candidate = base_path / name
                if name in excluded_names or candidate.is_symlink() or is_excluded(candidate, config):
                    continue
                kept.append(name)
            dirs[:] = kept
            for name in files:
                path = base_path / name
                if path.suffix.lower() not in allowed or path.is_symlink() or is_excluded(path, config):
                    continue
                yield path

def source_root_for(path, config):
    matches = []
    resolved = path.resolve()
    for raw in config["scan_roots"]:
        root = Path(raw).resolve()
        if resolved == root or root in resolved.parents:
            matches.append(root)
    return max(matches, key=lambda p: len(p.parts)) if matches else Path(path.anchor)

def origin_for(path, config):
    parts = path.parts
    resolved = path.resolve()
    ai_roots = [Path(p).resolve() for p in config.get("ai_workspace_roots", [])]
    in_ai_workspace = any(resolved == root or root in resolved.parents for root in ai_roots)
    if in_ai_workspace:
        if "outputs" in parts and FINAL_MARK.search(path.name):
            return "confirmed", "dsh_workspace_final_or_receipt"
        if "outputs" in parts:
            return "probable", "dsh_workspace_output_requires_final_review"
        return "unknown", "dsh_workspace_non_output"
    lower = path.as_posix().lower()
    if any(x in lower for x in ("openviking", "deepseek", "dsh")) and "outputs" in parts:
        return "probable", "ai_named_output_directory"
    return "unknown", "path_alone_cannot_prove_ai_origin"

SF_DATALESS = 0x40000000

def cached_hash(db, path, stat, max_bytes):
    # Reading a dataless FileProvider/iCloud placeholder can trigger a large
    # network download. Ledger discovery must never materialize cloud files.
    if getattr(stat, 'st_flags', 0) & SF_DATALESS:
        return None, 'dataless_cloud_file_not_downloaded', False
    if stat.st_size > max_bytes:
        return None, "oversize_hash_requires_review", False
    key = path.as_posix()
    row = db.execute("SELECT sha256 FROM file_cache WHERE path=? AND device=? AND inode=? AND size_bytes=? AND mtime_ns=?",
        (key, stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)).fetchone()
    if row:
        return row[0], None, True
    before = (stat.st_size, stat.st_mtime_ns)
    digest = sha256(path)
    after = path.stat()
    if (after.st_size, after.st_mtime_ns) != before:
        raise RuntimeError("changed_during_hash")
    db.execute("INSERT OR REPLACE INTO file_cache(path,device,inode,size_bytes,mtime_ns,sha256) VALUES(?,?,?,?,?,?)",
        (key, stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, digest))
    return digest, None, False

def existing_repo_hashes(root=ROOT):
    result = {}
    for name in ("assets", "outputs", "docs"):
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.stat().st_size <= 104857600:
                result.setdefault(sha256(path), []).append(path.relative_to(root).as_posix())
    return result

def find_artifact(db, path, stat, digest):
    if stat:
        rows = db.execute("SELECT artifact_id,path,present FROM locations WHERE device=? AND inode=? ORDER BY last_seen DESC",
            (stat.st_dev, stat.st_ino)).fetchall()
        if rows:
            return rows[0][0], "same_inode", rows
    if digest:
        rows = db.execute("SELECT v.artifact_id,l.path,l.present FROM versions v LEFT JOIN locations l ON l.artifact_id=v.artifact_id WHERE v.sha256=? ORDER BY v.last_seen DESC", (digest,)).fetchall()
        if len({row[0] for row in rows}) == 1 and rows:
            return rows[0][0], "same_unique_sha256", rows
    return None, "new_artifact", []

def observe(path, config, db, repo_hashes):
    stat = path.stat()
    digest = None
    errors = []
    cache_hit = False
    try:
        digest, hash_note, cache_hit = cached_hash(db, path, stat, config["max_auto_hash_bytes"])
        if hash_note:
            errors.append(hash_note)
    except (OSError, RuntimeError) as exc:
        errors.append(str(exc))
    artifact_id, match_reason, identity_rows = find_artifact(db, path, stat, digest)
    new_artifact = artifact_id is None
    previous_path_state = db.execute("SELECT status,origin_confidence,origin_reason FROM observations WHERE path=? ORDER BY observed_at DESC LIMIT 1", (path.as_posix(),)).fetchone()
    if new_artifact:
        artifact_id = uuid.uuid4().hex
    origin, origin_reason = origin_for(path, config)
    ext = path.suffix.lower()
    if errors == ['dataless_cloud_file_not_downloaded']:
        status = "held_cloud_not_local"
    elif errors:
        status = "held_read"
    elif digest in repo_hashes:
        status = "already_in_knowledge"
    elif PERSONAL_PATH.search(path.as_posix()) or SECRET_PATH.search(path.as_posix()):
        status = "held_sensitive_path"
    elif ext in IMAGE_EXTS:
        status = "held_binary_review"
    elif origin != "confirmed":
        status = "held_origin_review"
    elif ext not in TEXT_EXTS | OFFICE_EXTS:
        status = "held_format_review"
    else:
        status = "eligible_reviewed_intake"
    if not new_artifact:
        previous_locations = db.execute("SELECT path FROM locations WHERE artifact_id=?", (artifact_id,)).fetchall()
        previously_seen_here = any(row[0] == path.as_posix() for row in previous_locations)
        old_hash = db.execute("SELECT current_sha256 FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()[0]
        # A second location with the same bytes is a duplicate, not a changed version.
        if previously_seen_here and old_hash and digest and old_hash != digest and status != "already_in_knowledge":
            status = "held_changed_version"
    now = utcnow()
    if new_artifact:
        db.execute("INSERT INTO artifacts(artifact_id,first_seen,last_seen,origin_confidence,origin_reason,current_status,current_sha256,current_path) VALUES(?,?,?,?,?,?,?,?)",
            (artifact_id, now, now, origin, origin_reason, status, digest, path.as_posix()))
    else:
        db.execute("UPDATE artifacts SET last_seen=?,current_status=?,current_sha256=COALESCE(?,current_sha256),current_path=? WHERE artifact_id=?",
            (now, status, digest, path.as_posix(), artifact_id))
    location = db.execute("SELECT location_id,present,path FROM locations WHERE path=?", (path.as_posix(),)).fetchone()
    if location:
        db.execute("UPDATE locations SET artifact_id=?,last_seen=?,present=1,device=?,inode=?,relation=? WHERE location_id=?",
            (artifact_id, now, stat.st_dev, stat.st_ino, match_reason, location[0]))
    else:
        db.execute("INSERT INTO locations(location_id,artifact_id,path,device,inode,first_seen,last_seen,present,relation) VALUES(?,?,?,?,?,?,?,1,?)",
            (uuid.uuid4().hex, artifact_id, path.as_posix(), stat.st_dev, stat.st_ino, now, now, match_reason))
    movement_detected = False
    if identity_rows:
        for row in identity_rows:
            if row[1] == path.as_posix() or row[2] != 1:
                continue
            try:
                previous = Path(row[1]).stat()
                if (previous.st_dev, previous.st_ino) == (stat.st_dev, stat.st_ino):
                    continue  # hard link or retained copy, not a move
            except OSError:
                pass
            movement_detected = True
            db.execute("UPDATE locations SET present=0,last_seen=? WHERE artifact_id=? AND path=?",
                (now, artifact_id, row[1]))
    if digest:
        version = db.execute("SELECT version_id FROM versions WHERE artifact_id=? AND sha256=? AND size_bytes=? AND mtime_ns=?",
            (artifact_id, digest, stat.st_size, stat.st_mtime_ns)).fetchone()
        if version:
            db.execute("UPDATE versions SET last_seen=? WHERE version_id=?", (now, version[0]))
        else:
            db.execute("INSERT INTO versions(version_id,artifact_id,sha256,size_bytes,mtime_ns,first_seen,last_seen) VALUES(?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, artifact_id, digest, stat.st_size, stat.st_mtime_ns, now, now))
    unchanged = bool(location and previous_path_state == (status, origin, origin_reason) and (cache_hit or status == 'held_cloud_not_local'))
    observation_id = None if unchanged else uuid.uuid4().hex
    if not unchanged:
        db.execute("INSERT INTO observations(observation_id,artifact_id,path,observed_at,status,reasons_json,sha256,size_bytes,mtime_ns,device,inode,origin_confidence,origin_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (observation_id, artifact_id, path.as_posix(), now, status, json.dumps(errors, ensure_ascii=False), digest,
             stat.st_size, stat.st_mtime_ns, stat.st_dev, stat.st_ino, origin, origin_reason))
    return {"artifact_id": artifact_id, "observation_id": observation_id, "path": path.as_posix(),
        "sha256": digest, "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
        "device": stat.st_dev, "inode": stat.st_ino, "status": status, "reasons": errors,
        "origin_confidence": origin, "origin_reason": origin_reason,
        "match_reason": match_reason, "cache_hit": cache_hit, "unchanged": unchanged,
        "movement_detected": movement_detected,
        "source_root": source_root_for(path, config).as_posix()}

def mark_missing(db, seen_paths):
    now = utcnow()
    rows = db.execute("SELECT artifact_id,path,device,inode FROM locations WHERE present=1").fetchall()
    missing = 0
    for artifact_id, path, device, inode in rows:
        if path in seen_paths:
            continue
        # A duplicate/hard link need not be re-observed at every location in
        # each scan. Only mark it absent when the physical identity is gone.
        try:
            stat = Path(path).stat()
            if (stat.st_dev, stat.st_ino) == (device, inode):
                continue
        except OSError:
            pass
        db.execute("UPDATE locations SET present=0,last_seen=? WHERE artifact_id=? AND path=?", (now, artifact_id, path))
        db.execute("UPDATE artifacts SET current_status='missing_observed_not_deleted',last_seen=? WHERE artifact_id=?", (now, artifact_id))
        missing += 1
    return missing

def mask_name(path):
    name = Path(path).name
    return re.sub(r"[0-9a-f]{32,}", "[hash]", name, flags=re.I)[:120]

def write_if_changed(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding='utf-8') == content:
        return False
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(content, encoding='utf-8')
    os.replace(temp, path)
    return True

def write_public_summary(records, stats):
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter(r["status"] for r in records)
    origins = Counter(r["origin_confidence"] for r in records)
    lines = [
      "---", "title: DSH 全盘 AI 产出总账",
      "description: DSH 主账的脱敏汇总；完整路径仅在本机，OpenKnowledge 跟从展示。",
      "tags:", "  - 主题-系统运维", "  - 类型-产出总账", "  - 状态-自动生成",
      "category: 系统运维", "document_type: 产出总账", "lifecycle: 自动生成",
      "search_scope: 私有Git", "type: note", "---", "",
      "# DSH 全盘 AI 产出总账", "",
      "> 本页由 DSH 总账生成；OpenKnowledge 跟从展示。完整源路径和原始回执只保存在本机状态区。", "",
      "- 总账指纹：" + stats["content_fingerprint"],
      "- 本轮候选：" + str(stats["candidate_count"]) + " 件",
      "- 唯一 artifact：" + str(stats["unique_artifact_count"]) + " 个",
      "- 文件身份匹配：" + str(stats["same_inode_count"]) + " 件；其中移动/改名：" + str(stats["moved_or_renamed_count"]) + " 件；唯一哈希关联：" + str(stats["same_hash_count"]) + " 件",
      "- 哈希缓存命中：" + str(stats["cache_hits"]) + " 件；读取错误：" + str(stats["read_errors"]) + " 件",
      "- 原件策略：只读发现，不移动、不删除、不改名。", "",
      "## 接收状态", "",
      "| 状态 | 文件数 | 含义 |", "|---|---:|---|",
    ]
    labels = {
      "eligible_reviewed_intake": "来源明确，可进入安全接收复核",
      "already_in_knowledge": "知识仓已有同内容，不重复收录",
      "held_origin_review": "AI 来源未确认，等待人工判断",
      "held_sensitive_path": "路径显示可能敏感，默认留在本地",
      "held_binary_review": "图片等二进制内容需人工查看",
      "held_changed_version": "内容变化，不能静默覆盖旧接收版",
      "held_read": "读取或哈希失败",
      "held_cloud_not_local": "iCloud 占位文件，只登记，不触发下载",
      "held_format_review": "格式需复核",
      "candidate": "候选",
    }
    for status, count in sorted(counts.items()):
        lines.append("| " + status + " | " + str(count) + " | " + labels.get(status, "需复核") + " |")
    lines += ["", "## AI 来源分级", "", "| 级别 | 文件数 |", "|---|---:|"]
    for origin, count in sorted(origins.items()):
        lines.append("| " + origin + " | " + str(count) + " |")
    lines += ["", "## 边界", "",
      "- confirmed 仅表示路径和成果标记能证明来自 DSH 定稿/回执区，不证明业务内容已获维护者放行。",
      "- unknown 不是非 AI，而是没有足够证据，不会擅自上传。",
      "- 自动接收开关首扫保持关闭；清单确认后再按安全门接入。",
      "- 详细文件身份与路径在本机 SQLite 总账，不在本页暴露。", "",
      "[查看待确认清单](./待确认清单.md)", ""]
    write_if_changed(SUMMARY, "\n".join(lines))
    pending = ["---", "title: 待确认清单（脱敏）",
      "description: 仅汇总待确认数量与原因，不公开源路径或文件名单。",
      "tags:", "  - 主题-系统运维", "  - 类型-待确认清单", "  - 状态-自动生成",
      "category: 系统运维", "document_type: 待确认清单", "lifecycle: 自动生成",
      "search_scope: 私有Git", "type: note", "---", "",
      "# 待确认清单（脱敏）", "",
      "以下只列数量与原因，不公开完整源路径或文件名单。完整清单在本机总账定位。", "",
      "| 汇总项 | 数量 | 状态 | 说明 |", "|---|---|---|---|"]
    review_counts = Counter(rec["status"] for rec in records if rec["status"].startswith("held"))
    for status, count in sorted(review_counts.items()):
        pending.append("| 按状态汇总 | " + str(count) + " 件 | " + status + " | 完整清单见本机总账 |")
    if not review_counts:
        pending.append("| — | 当前没有待确认项 | — | — |")
    pending += ["", "完整路径见本机 output-ledger-report.json；此文件不进入 OpenViking。", ""]
    write_if_changed(PENDING, "\n".join(pending))

def scan(config_path=CONFIG_PATH, db_path=DB_PATH, root=ROOT):
    config = load_config(config_path)
    db = init_db(db_path)
    started = utcnow()
    repo_hashes = existing_repo_hashes(root)
    records = []
    errors = []
    try:
        for path in walk_candidates(config):
            try:
                records.append(observe(path, config, db, repo_hashes))
                if len(records) % 1000 == 0:
                    db.commit()
            except Exception as exc:
                errors.append({"path": path.as_posix(), "error": str(exc)})
        missing = mark_missing(db, {r["path"] for r in records})
        db.commit()
    finally:
        db.close()
    content_fingerprint = hashlib.sha256("\n".join(sorted(r["artifact_id"] + ":" + str(r["sha256"]) + ":" + r["path"] + ":" + r["status"] for r in records)).encode("utf-8")).hexdigest()
    stats = {
      "started_at": started, "finished_at": utcnow(), "content_fingerprint": content_fingerprint,
      "candidate_count": len(records),
      "unique_artifact_count": len({r["artifact_id"] for r in records}),
      "same_inode_count": sum(r["match_reason"] == "same_inode" for r in records),
      "moved_or_renamed_count": sum(r.get("movement_detected", False) for r in records),
      "same_hash_count": sum(r["match_reason"] == "same_unique_sha256" for r in records),
      "cache_hits": sum(r["cache_hit"] for r in records),
      "observations_written": sum(not r.get("unchanged") for r in records),
      "read_errors": len(errors) + sum(r["status"] == "held_read" for r in records),
      "dataless_cloud_files": sum(r["status"] == "held_cloud_not_local" for r in records),
      "missing_locations": missing,
      "auto_intake": bool(config.get("auto_intake")),
      "status_counts": dict(Counter(r["status"] for r in records)),
      "origin_counts": dict(Counter(r["origin_confidence"] for r in records)),
    }
    report = {"status": "pass" if not errors else "partial", "stats": stats,
      "config": {"scan_roots": config["scan_roots"], "excluded_roots": config["excluded_roots"]},
      "records": records, "errors": errors,
      "privacy": "full paths stay in local state; public summary is sanitized",
      "source_policy": "read-only; no move, rename or deletion"}
    RAW_REPORT.parent.mkdir(parents=True, exist_ok=True)
    temp = RAW_REPORT.with_suffix(".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, RAW_REPORT)
    write_public_summary(records, stats)
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()
    if not args.scan:
        parser.error("choose --scan")
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'output-ledger.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'status': 'skipped', 'reason': 'another_output_ledger_scan_is_running'}))
            return 0
        report = scan(Path(args.config), Path(args.db))
        print(json.dumps({"status": report["status"], "stats": report["stats"],
            "raw_report": str(RAW_REPORT), "public_summary": str(SUMMARY)}, ensure_ascii=False))
        return 0 if report["status"] == "pass" else 2

if __name__ == "__main__":
    sys.exit(main())
