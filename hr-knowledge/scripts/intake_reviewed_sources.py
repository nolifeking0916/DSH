#!/usr/bin/env python3
"""Copy explicitly reviewed source files without modifying the originals.

The allowlist binds an exact source path, target path and SHA-256. Any source
change stops the sync for review instead of silently overwriting the target.
Targets live under outputs/, which sync_online.py keeps out of OpenViking.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "reviewed_sources.json"
STATE = Path.home() / "Library" / "Application Support" / "hr-knowledge-sync"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contained(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("absolute paths and parent traversal are forbidden")
    root = root.resolve()
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError("path escapes its declared root")
    return path


def load_manifest(path: Path = MANIFEST) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("version") != 1 or value.get("cloud_search") is not False:
        raise ValueError("reviewed source manifest must be version 1 and cloud_search=false")
    if value.get("target_root") != "outputs":
        raise ValueError("reviewed sources may only target git-only outputs/")
    targets = [record.get("target") for record in value.get("records", [])]
    if len(targets) != len(set(targets)):
        raise ValueError("duplicate reviewed target")
    return value


def copy_reviewed(manifest_path: Path = MANIFEST, root: Path = ROOT) -> dict:
    manifest = load_manifest(manifest_path)
    source_root = Path(manifest["source_root"]).resolve()
    target_root = contained(root, manifest["target_root"])
    records = []
    for item in manifest["records"]:
        source = contained(source_root, item["source"])
        target = contained(target_root, item["target"])
        expected = item["sha256"].lower()
        result = {"source": item["source"], "target": item["target"], "status": "pending"}
        try:
            if not source.is_file():
                raise ValueError("reviewed source is missing")
            before = sha256(source)
            if before != expected:
                raise ValueError("source hash changed; renewed review required")
            if target.exists():
                if not target.is_file() or sha256(target) != expected:
                    raise ValueError("target differs; refusing to overwrite")
                result["status"] = "unchanged"
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + ".reviewed-intake-tmp")
                try:
                    with source.open("rb") as src, temporary.open("xb") as dst:
                        for chunk in iter(lambda: src.read(1024 * 1024), b""):
                            dst.write(chunk)
                        dst.flush()
                        os.fsync(dst.fileno())
                    if sha256(temporary) != expected:
                        raise ValueError("temporary copy hash mismatch")
                    os.replace(temporary, target)
                finally:
                    if temporary.exists():
                        temporary.unlink()
                result["status"] = "copied"
            if sha256(source) != before or sha256(target) != expected:
                raise ValueError("post-copy source/target verification failed")
            result["sha256"] = expected
        except Exception as exc:
            result["status"] = "held"
            result["reason"] = str(exc)
        records.append(result)
    report = {
        "status": "fail" if any(r["status"] == "held" for r in records) else "pass",
        "cloud_search": False,
        "copied": sum(r["status"] == "copied" for r in records),
        "unchanged": sum(r["status"] == "unchanged" for r in records),
        "held": sum(r["status"] == "held" for r in records),
        "records": records,
    }
    STATE.mkdir(parents=True, exist_ok=True)
    temporary = STATE / "reviewed-intake-report.json.tmp"
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, STATE / "reviewed-intake-report.json")
    return report


def main() -> int:
    try:
        report = copy_reviewed()
    except Exception as exc:
        report = {"status": "fail", "error": str(exc)}
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    sys.exit(main())
