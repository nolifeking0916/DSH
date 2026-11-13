#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("DSH_CENTRAL_ROOT", str(Path.home() / ".dsh" / "DSH-central"))).resolve()
STATE = Path(os.environ.get("DSH_CENTRAL_STATE", str(Path.home() / ".dsh" / "state" / "dsh-central-sync"))).resolve()
REPORT = Path(os.environ.get("DSH_OUTPUT_LEDGER_REPORT", str(Path.home() / "Library" / "Application Support" / "hr-knowledge-sync" / "output-ledger-report.json"))).resolve()
KNOWLEDGE = Path("/Users/leto/WorkBuddy/HR技术中台/hr-knowledge")
WORKSPACE = Path(os.environ.get("DSH_OUTPUT_WORKSPACE", "/Users/leto/.dsh/bot/workspace")).resolve()
SELECTED = {"eligible_reviewed_intake", "already_in_knowledge"}
ALLOWED = {".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".docx", ".pptx", ".xlsx", ".pdf"}
KNOWLEDGE_ROOTS = ("outputs", "assets", "docs", "openspec", "migration")
SOURCE_ROOTS = [
    (WORKSPACE, "dsh-workspace"),
    (Path("/Users/leto/Documents/DSH"), "dsh-documents"),
    (Path("/Users/leto/Desktop"), "desktop"),
    (Path("/Users/leto/Documents"), "documents"),
    (Path("/Users/leto/Downloads"), "downloads"),
    (Path("/Users/leto/WorkBuddy"), "workbuddy"),
    (Path("/private/tmp"), "tmp"),
    (Path("/tmp"), "tmp"),
]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)

def knowledge_index():
    index = {}
    for name in KNOWLEDGE_ROOTS:
        base = KNOWLEDGE / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in ALLOWED:
                continue
            digest = sha256(path)
            index.setdefault(digest, []).append(path)
    for paths in index.values():
        paths.sort(key=lambda p: (KNOWLEDGE_ROOTS.index(p.relative_to(KNOWLEDGE).parts[0]), len(p.as_posix()), p.as_posix()))
    return index

def mapped_target(source: Path) -> Path:
    source = source.resolve()
    for root, label in SOURCE_ROOTS:
        try:
            rel = source.relative_to(root)
            break
        except ValueError:
            continue
    else:
        raise RuntimeError("source_root_not_allowlisted")
    if any(part in {".git", "node_modules", "__pycache__", ".venv", "venv"} for part in rel.parts):
        raise RuntimeError("excluded_source_directory")
    clean = [re.sub(r"[\x00-\x1f\\]", "_", part) for part in rel.parts]
    return Path(label, *clean)

def choose(records):
    index = knowledge_index()
    chosen = {}
    errors = []
    candidate_errors = {}
    for rec in records:
        if rec.get("status") not in SELECTED:
            continue
        if rec.get("status") == "eligible_reviewed_intake" and rec.get("origin_confidence") not in {"confirmed", "probable"}:
            continue
        digest = rec.get("sha256")
        artifact = rec.get("artifact_id")
        if not digest or not artifact:
            errors.append({"reason": "missing_content_hash", "status": rec.get("status")})
            continue
        key = artifact + ":" + digest
        repo_match = index.get(digest, []) if rec.get("status") == "already_in_knowledge" else []
        try:
            if repo_match:
                source = repo_match[0]
                target = Path("hr-knowledge") / source.relative_to(KNOWLEDGE)
                rank = 0
            else:
                source = Path(rec["path"]).resolve()
                target = mapped_target(source)
                rank = 1 if rec.get("status") == "eligible_reviewed_intake" else 2
            if not source.is_file():
                raise RuntimeError("source_not_local_file")
            if source.suffix.lower() not in ALLOWED:
                raise RuntimeError("extension_not_allowed")
            size = source.stat().st_size
            if size > 100 * 1024 * 1024:
                raise RuntimeError("github_100mib_block")
            if sha256(source) != digest:
                raise RuntimeError("source_changed_since_ledger_scan")
            item = {"key": key, "artifact_id": artifact, "sha256": digest, "bytes": size,
                    "source": str(source), "target": target.as_posix(), "origin_status": rec["status"], "rank": rank}
            if key not in chosen or rank < chosen[key]["rank"]:
                chosen[key] = item
        except Exception as exc:
            candidate_errors.setdefault(key, []).append({"reason": str(exc), "source": rec.get("path"), "status": rec.get("status")})
    for key, failures in candidate_errors.items():
        if key not in chosen:
            errors.extend(failures[:1])
    items = sorted(chosen.values(), key=lambda x: x["target"])
    targets = {}
    for item in items:
        if item["target"] in targets and targets[item["target"]] != item["key"]:
            errors.append({"reason": "target_collision", "target": item["target"]})
        targets[item["target"]] = item["key"]
    return items, errors

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    report_path = REPORT
    ledger = json.loads(report_path.read_text(encoding="utf-8"))
    records = ledger.get("records", [])
    items, errors = choose(records)
    exclusions_path = STATE / "excluded-targets.json"
    excluded_targets = {x["target"] for x in json.loads(exclusions_path.read_text(encoding="utf-8")).get("excluded", [])} if exclusions_path.is_file() else set()
    items = [x for x in items if x["target"] not in excluded_targets]
    previous_path = STATE / "projected-manifest.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")).get("entries", []) if previous_path.is_file() else []
    # An explicit exclusion is the reviewed scope decision, not an implicit source deletion.
    # Never copy or delete the central copy as a side effect of this filter.
    previous = [x for x in previous if x["target"] not in excluded_targets]
    old_by_key = {x["key"]: x for x in previous}
    new_targets = {x["target"] for x in items}
    renames = []
    superseded = {}
    for item in items:
        old = old_by_key.get(item["key"])
        if not old:
            same_artifact = [x for x in previous if x["artifact_id"] == item["artifact_id"]]
            if len(same_artifact) == 1:
                old = same_artifact[0]
        if old:
            superseded[item["key"]] = old
            if old["target"] != item["target"]:
                renames.append({"old": old["target"], "new": item["target"], "key": item["key"]})
    deletions = [x for x in previous if x["target"] not in new_targets and x["key"] not in {o["key"] for o in superseded.values()}]
    if deletions:
        errors.extend({"reason": "deletion_or_scope_change_requires_review", "target": x["target"]} for x in deletions)
    if args.apply and not errors:
        for rename in renames:
            old, new = ROOT / rename["old"], ROOT / rename["new"]
            if old.exists():
                if new.exists():
                    errors.append({"reason": "rename_target_collision", "target": rename["new"]})
                    continue
                new.parent.mkdir(parents=True, exist_ok=True)
                os.replace(old, new)
        for item in items:
            target = ROOT / item["target"]
            if target.exists():
                if sha256(target) == item["sha256"]:
                    continue
                old = superseded.get(item["key"])
                if not old:
                    errors.append({"reason": "existing_target_identity_mismatch", "target": item["target"]})
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(".dsh-tmp-" + next(tempfile._get_candidate_names()))
            try:
                shutil.copy2(item["source"], tmp)
                if sha256(tmp) != item["sha256"]:
                    raise RuntimeError("copy_hash_mismatch")
                os.replace(tmp, target)
            finally:
                if tmp.exists():
                    tmp.unlink()
    entries = [{"key": x["key"], "artifact_id": x["artifact_id"], "target": x["target"],
                "sha256": x["sha256"], "bytes": x["bytes"], "origin_status": x["origin_status"]} for x in items]
    summary = {"schema_version": 1, "file_count": len(entries), "total_bytes": sum(x["bytes"] for x in entries),
               "extensions": dict(sorted(Counter(Path(x["target"]).suffix.lower() for x in entries).items())),
               "over_50_mib": sum(x["bytes"] > 50 * 1024 * 1024 for x in entries),
               "over_100_mib": sum(x["bytes"] > 100 * 1024 * 1024 for x in entries)}
    if args.apply and not errors:
        save_json(ROOT / "manifests" / "sync-manifest.json", {"schema_version": 1, "entries": entries})
        save_json(ROOT / "manifests" / "summary.json", summary)
        save_json(previous_path, {"schema_version": 1, "entries": entries})
        save_json(STATE / "allowed-renames.json", {"renames": [{"old": x["old"], "new": x["new"]} for x in renames]})
    excluded = Counter(x.get("status") for x in records if x.get("status") not in SELECTED)
    full = {"status": "held" if errors else ("projected" if args.apply else "ready"),
            "generated_at": datetime.now(timezone.utc).isoformat(), "source_report": str(report_path),
            "summary": summary, "selected_locations": sum(x.get("status") in SELECTED for x in records),
            "selected_by_status": dict(Counter(x.get("status") for x in records if x.get("status") in SELECTED)),
            "safety_excluded_targets": len(excluded_targets),
            "excluded_by_status": dict(excluded), "renames": renames, "deletions": deletions,
            "errors": errors, "items": items}
    save_json(STATE / "projection-report.json", full)
    print(json.dumps({"status": full["status"], **summary, "selected_locations": full["selected_locations"],
                      "selected_by_status": full["selected_by_status"], "rename_count": len(renames),
                      "deletion_count": len(deletions), "error_count": len(errors),
                      "report": str(STATE / "projection-report.json")}, ensure_ascii=False))
    return 2 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
