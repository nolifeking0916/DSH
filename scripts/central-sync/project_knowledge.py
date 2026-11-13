#!/usr/bin/env python3
"""Project the living hr-knowledge working tree into the central DSH repository.

The source is never modified. Safety is evaluated before copying. Deletions,
ambiguous renames, identity conflicts and sensitive content hold the whole run.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from safety_rules import extract, sha256, RESTRICTED_RE, SECRET_RES, PERSONAL_RES, KNOWN_NAMES
from sync_online import ALLOWED, TEXT_EXTS, CODE_EXTS, save_json

ROOT = Path(os.environ.get("DSH_CENTRAL_ROOT", str(Path.home() / ".dsh" / "DSH-central"))).resolve()
STATE = Path(os.environ.get("DSH_CENTRAL_STATE", str(Path.home() / ".dsh" / "state" / "dsh-central-sync"))).resolve()
SOURCE = Path(os.environ.get("DSH_CENTRAL_KNOWLEDGE_SOURCE", "/Users/leto/WorkBuddy/HR技术中台/hr-knowledge")).resolve()
TARGET_ROOT = "hr-knowledge"
EXCLUDED_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
SF_DATALESS = 0x40000000
MAX_BYTES = 100 * 1024 * 1024


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def source_paths():
    if not SOURCE.is_dir():
        raise RuntimeError("knowledge_source_not_directory")
    if (SOURCE / ".git").exists():
        # 中央仓接管 Git 后，源仓新文件可能尚未提交；纳入非忽略未跟踪文件，
        # 同时让 .gitignore/.git/info/exclude 继续排除运行缓存。所有文件仍逐件过安全门。
        raw = subprocess.check_output(["git", "-C", str(SOURCE), "ls-files", "-z", "--cached", "--others", "--exclude-standard"])
        for item in raw.split(b"\0"):
            if not item:
                continue
            path = SOURCE / os.fsdecode(item)
            if path.is_file() and not any(part in EXCLUDED_DIRS for part in path.relative_to(SOURCE).parts):
                yield path
        return
    for base, dirs, files in os.walk(SOURCE, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        for name in sorted(files):
            path = Path(base) / name
            if any(part in EXCLUDED_DIRS for part in path.relative_to(SOURCE).parts):
                continue
            yield path


def exceptions():
    value = load_json(STATE / "review-exceptions.json", [])
    return {(x.get("target"), x.get("sha256")): set(x.get("reasons", [])) for x in value}


def inspect(path: Path, reviewed):
    relative = path.relative_to(SOURCE).as_posix()
    target = (Path(TARGET_ROOT) / relative).as_posix()
    ext = path.suffix.lower()
    reasons = []
    text = ""
    digest = ""
    size = 0
    try:
        stat = path.stat()
        size = stat.st_size
        if path.is_symlink():
            reasons.append("symlink_requires_manual_review")
        if getattr(stat, "st_flags", 0) & SF_DATALESS:
            reasons.append("dataless_cloud_file_not_downloaded")
        if size > MAX_BYTES:
            reasons.append("github_100mib_block")
        if ext not in ALLOWED:
            reasons.append("unsupported_requires_manual_review")
        if ext not in CODE_EXTS and RESTRICTED_RE.search(target):
            reasons.append("restricted_personnel_or_credential_path")
        if not reasons:
            digest = sha256(path)
            if size == 0:
                text = ""
            elif ext in TEXT_EXTS:
                text = path.read_text(encoding="utf-8", errors="replace")
            else:
                text, error = extract(path)
                if error:
                    reasons.append(error)
            if size > 0 and not text.strip() and ext != ".pdf":
                reasons.append("empty_text_extraction")
            if any(r.search(text) for r in SECRET_RES):
                reasons.append("possible_secret")
            personal_text = re.sub(r"(?i)\b[0-9a-f]{32,}\b", "", text)
            if ext not in CODE_EXTS and any(r.search(personal_text) for r in PERSONAL_RES):
                reasons.append("possible_personal_data")
            if ext not in CODE_EXTS and any(n in text or n in target for n in KNOWN_NAMES):
                reasons.append("known_person_name")
    except OSError as exc:
        reasons.append("read_failed:" + type(exc).__name__)
    waived = reviewed.get((target, digest), set())
    applied_waivers = sorted(waived & set(reasons))
    reasons = sorted(set(reasons) - waived)
    return {
        "source_relative": relative,
        "target": target,
        "sha256": digest,
        "bytes": size,
        "reasons": reasons,
        "waived": applied_waivers,
    }


def plan_items():
    items = []
    errors = []
    reviewed = exceptions()
    for path in source_paths():
        item = inspect(path, reviewed)
        items.append(item)
        if item["reasons"]:
            errors.append({"target": item["target"], "sha256": item["sha256"], "reasons": item["reasons"]})
    if not items:
        errors.append({"target": TARGET_ROOT, "reasons": ["empty_source_requires_manual_review"]})
    return items, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    items, errors = plan_items()
    previous = load_json(STATE / "knowledge-manifest.json", {}).get("entries", [])
    old_by_target = {x["target"]: x for x in previous}
    current_by_target = {x["target"]: x for x in items}
    current_targets = set(current_by_target)
    clean_targets = {x["target"] for x in items if not x["reasons"]}
    old_targets = set(old_by_target)

    renames = []
    deletions = []
    used_new = set()
    for old in previous:
        if old["target"] in current_targets:
            continue
        matches = [x for x in items if not x["reasons"] and x["target"] not in old_targets
                   and x["target"] not in used_new and x["sha256"] and x["sha256"] == old.get("sha256")]
        if len(matches) == 1:
            new = matches[0]
            renames.append({"old": old["target"], "new": new["target"], "sha256": old["sha256"]})
            used_new.add(new["target"])
        else:
            deletions.append({"target": old["target"], "reason": "deletion_or_ambiguous_rename_requires_review"})
    if deletions:
        errors.extend(deletions)

    for item in items:
        if item["reasons"] or item["target"] not in clean_targets:
            continue
        target = ROOT / item["target"]
        if not target.exists():
            continue
        if sha256(target) == item["sha256"]:
            continue
        old = old_by_target.get(item["target"])
        if not old:
            errors.append({"target": item["target"], "reasons": ["existing_target_identity_mismatch"]})
        elif old.get("sha256") != item["sha256"] and old.get("bytes") == item["bytes"] and old.get("source_relative") != item["source_relative"]:
            errors.append({"target": item["target"], "reasons": ["source_identity_changed_without_rename_review"]})

    if args.apply and not errors:
        for rename in renames:
            if (ROOT / rename["new"]).exists():
                errors.append({"target": rename["new"], "reasons": ["rename_target_collision"]})
        for item in items:
            if not item["reasons"] and sha256(SOURCE / item["source_relative"]) != item["sha256"]:
                errors.append({"target": item["target"], "reasons": ["source_changed_during_projection"]})
        if not errors:
            for rename in renames:
                old_path = ROOT / rename["old"]
                new_path = ROOT / rename["new"]
                if old_path.exists():
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(old_path, new_path)
            for item in items:
                if item["reasons"]:
                    continue
                target = ROOT / item["target"]
                if target.exists() and sha256(target) == item["sha256"]:
                    continue
                source = SOURCE / item["source_relative"]
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_name(".dsh-central-tmp-" + next(tempfile._get_candidate_names()))
                try:
                    shutil.copy2(source, tmp)
                    if sha256(tmp) != item["sha256"] or sha256(source) != item["sha256"]:
                        raise RuntimeError("source_or_copy_hash_mismatch:" + item["target"])
                    os.replace(tmp, target)
                finally:
                    if tmp.exists():
                        tmp.unlink()
            entries = [{k: x[k] for k in ("source_relative", "target", "sha256", "bytes")}
                       for x in items if not x["reasons"]]
            save_json(STATE / "knowledge-manifest.json", {"schema_version": 1, "entries": entries})
            save_json(STATE / "knowledge-allowed-renames.json", {"renames": renames})

    clean = [x for x in items if not x["reasons"]]
    summary = {
        "file_count": len(clean),
        "total_bytes": sum(x["bytes"] for x in clean),
        "extensions": dict(sorted(Counter(Path(x["target"]).suffix.lower() for x in clean).items())),
        "over_50_mib": sum(x["bytes"] > 50 * 1024 * 1024 for x in clean),
        "over_100_mib": sum(x["bytes"] > MAX_BYTES for x in clean),
    }
    status = "held" if errors else ("projected" if args.apply else "ready")
    report = {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(SOURCE),
        "summary": summary,
        "renames": renames,
        "deletions": deletions,
        "errors": errors,
        "items": items,
    }
    save_json(STATE / "knowledge-projection-report.json", report)
    print(json.dumps({
        "status": status,
        **summary,
        "blocked_count": len(errors),
        "rename_count": len(renames),
        "deletion_count": len(deletions),
        "report": str(STATE / "knowledge-projection-report.json"),
    }, ensure_ascii=False))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
