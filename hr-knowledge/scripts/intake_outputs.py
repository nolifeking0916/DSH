#!/usr/bin/env python3
"""Intake only finalized/evidence artifacts from the legacy outputs folder.

Candidates are fail-closed scanned before any copy. Existing final artifacts are
immutable: changed source bytes or destination collisions require human review.
No source or cloud deletion is ever performed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from migrate_curated import (
    extract, sha256, RESTRICTED_RE, SECRET_RES, PERSONAL_RES, KNOWN_NAMES,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("/Users/leto/.dsh/bot/workspace/work/hr-data-center/outputs")
STATE = Path.home() / "Library" / "Application Support" / "hr-knowledge-sync"
REPORT = STATE / "intake-report.json"
ALLOWED = {".md", ".markdown", ".txt", ".docx", ".pptx", ".xlsx", ".pdf"}
TEXT_EXTS = {".md", ".markdown", ".txt"}
SELECT_RE = re.compile(r"\.(?:final|receipt|provenance)\.[^.]+$", re.I)


def save_json(value):
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, REPORT)


def semantic_target(name):
    path = Path(name)
    evidence = ".receipt." in name.lower() or ".provenance." in name.lower()
    if path.parent != Path("."):
        folder = Path("docs/evidence/nested") / path.parent
    else:
        folder = Path("docs/evidence/final") if evidence else Path("docs/current/final")
    leaf = path.name if path.suffix.lower() in TEXT_EXTS else path.stem + ".md"
    return folder / leaf


def inspect(path):
    rel = path.relative_to(SOURCE).as_posix()
    digest = sha256(path)
    text, error = extract(path)
    reasons = []
    if path.suffix.lower() not in ALLOWED:
        reasons.append("unsupported_requires_manual_review")
    if RESTRICTED_RE.search(rel):
        reasons.append("restricted_personnel_or_credential_path")
    if error:
        reasons.append(error)
    if not text.strip() and path.suffix.lower() != ".pdf":
        reasons.append("empty_text_extraction")
    if any(r.search(text) for r in SECRET_RES):
        reasons.append("possible_secret")
    personal_scan_text = re.sub(r"(?i)\b[0-9a-f]{32,}\b", "", text)
    if any(r.search(personal_scan_text) for r in PERSONAL_RES):
        reasons.append("possible_personal_data")
    if any(n in text or n in rel for n in KNOWN_NAMES):
        reasons.append("known_person_name")
    targets = [Path("outputs") / rel, semantic_target(rel)]
    collisions = []
    for target in targets:
        dest = ROOT / target
        if not dest.exists():
            continue
        if target.parts[0] == "outputs":
            same = sha256(dest) == digest
        elif path.suffix.lower() in TEXT_EXTS:
            same = dest.read_text(encoding="utf-8", errors="replace") == text
        else:
            status = "evidence" if target.parts[:2] == ("docs", "evidence") else "final"
            expected = "# " + path.stem + "\n\n> status: " + status + "; source_sha256: " + digest + "\n\n" + text
            same = dest.read_text(encoding="utf-8", errors="replace") == expected
        if not same:
            collisions.append(target.as_posix())
    if collisions:
        reasons.extend("destination_collision:" + p for p in collisions)
    return {
        "source": str(path), "sha256": digest, "bytes": path.stat().st_size,
        "targets": [p.as_posix() for p in targets], "text": text,
        "reasons": sorted(set(reasons)),
    }


def write_atomic(dest, data, source=None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".intake-tmp")
    if isinstance(data, str):
        tmp.write_text(data, encoding="utf-8")
    else:
        if source is None:
            raise ValueError("binary copy requires an explicit source")
        with source.open("rb") as src, tmp.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        shutil.copystat(source, tmp)
    os.replace(tmp, dest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    records = []
    if SOURCE.is_dir():
        for path in sorted(SOURCE.rglob("*"), key=lambda p: p.as_posix()):
            if path.is_file() and any(m in path.name.lower() for m in (".final.", ".receipt.", ".provenance.")):
                records.append(inspect(path))
    counts = Counter()
    copied = []
    for rec in records:
        if rec["reasons"]:
            counts["held"] += 1
            continue
        changed = []
        for target in rec["targets"]:
            dest = ROOT / target
            if dest.exists():
                continue
            if args.check_only:
                changed.append(target)
                continue
            source = Path(rec["source"])
            if target.startswith("outputs/"):
                write_atomic(dest, None, source)
            elif source.suffix.lower() in TEXT_EXTS:
                write_atomic(dest, rec["text"])
            else:
                evidence = target.startswith("docs/evidence/")
                status = "evidence" if evidence else "final"
                body = "# " + source.stem + "\n\n> status: " + status + "; source_sha256: " + rec["sha256"] + "\n\n" + rec["text"]
                write_atomic(dest, body)
            changed.append(target)
        if changed:
            counts["would_copy" if args.check_only else "copied"] += 1
            copied.extend(changed)
        else:
            counts["unchanged"] += 1
    public_records = [{k: v for k, v in r.items() if k != "text"} for r in records]
    report = {
        "status": "pass", "check_only": args.check_only,
        "candidate_count": len(records), "status_counts": dict(counts),
        "changed_targets": copied, "records": public_records,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "deletion_policy": "source deletions are ignored; cloud deletions require manual approval",
    }
    save_json(report)
    print(json.dumps({k: report[k] for k in ("status", "check_only", "candidate_count", "status_counts")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
