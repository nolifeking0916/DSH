#!/usr/bin/env python3
"""Fail-closed private Git + OpenViking sync for the curated HR knowledge repo.

Runtime state and raw CLI responses stay outside the online repository. No
credential is read or printed by this script. Cloud deletions are never issued.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

from migrate_curated import extract, sha256, RESTRICTED_RE, SECRET_RES, PERSONAL_RES, KNOWN_NAMES

ROOT = Path(__file__).resolve().parents[1]
STATE = Path.home() / "Library" / "Application Support" / "hr-knowledge-sync"
STATE_FILE = STATE / "state.json"
REPORT_FILE = STATE / "last-report.json"
PUBLISH_ROOTS = ("docs", "assets", "outputs", "openspec", "migration")
SEARCH_ROOTS = ("docs", "openspec", "migration")
ROOT_FILES = ("README.md", "AGENTS.md")
ALLOWED = {".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".docx", ".pptx", ".xlsx", ".pdf"}
TEXT_EXTS = {".md", ".markdown", ".txt", ".json", ".yaml", ".yml"}
CLOUD_PARENT = "viking://resources/hr-knowledge"


def run(args, timeout=120):
    return subprocess.run(args, cwd=ROOT, text=True, errors="replace",
                          capture_output=True, timeout=timeout)


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_state():
    try:
        value = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def candidates():
    files = [ROOT / p for p in ROOT_FILES]
    for name in PUBLISH_ROOTS:
        base = ROOT / name
        if base.exists():
            files.extend(p for p in base.rglob("*") if p.is_file())
    return sorted(set(files), key=lambda p: p.relative_to(ROOT).as_posix())


def ensure_word_previews(check_only=False):
    cmd = [sys.executable, str(ROOT / "scripts" / "word_previews.py")]
    if check_only:
        cmd.append("--check")
    proc = run(cmd, timeout=3600)
    save_json(STATE / "word-previews-invocation.json", {
        "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr,
    })
    if proc.returncode:
        raise RuntimeError("Word PDF preview generation failed: " + (proc.stderr.strip() or proc.stdout.strip())[-1000:])
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("Word preview generator returned invalid JSON")


def safety_scan():
    records = []
    blocked = []
    for path in candidates():
        rel = path.relative_to(ROOT).as_posix()
        if path.name == ".gitkeep":
            continue
        ext = path.suffix.lower()
        reasons = []
        if ext not in ALLOWED:
            reasons.append("unsupported_requires_manual_review")
        if RESTRICTED_RE.search(rel):
            reasons.append("restricted_personnel_or_credential_path")
        text, error = ((path.read_text(encoding="utf-8", errors="replace"), None) if ext in TEXT_EXTS else (extract(path) if ext in ALLOWED else ("", "unsupported_extension")))
        if ext in ALLOWED and error:
            reasons.append(error)
        if ext in ALLOWED and not text.strip() and ext != ".pdf":
            reasons.append("empty_text_extraction")
        if any(r.search(text) for r in SECRET_RES):
            reasons.append("possible_secret")
        personal_scan_text = re.sub(r"(?i)\b[0-9a-f]{32,}\b", "", text)
        if any(r.search(personal_scan_text) for r in PERSONAL_RES):
            reasons.append("possible_personal_data")
        if any(n in text or n in rel for n in KNOWN_NAMES):
            reasons.append("known_person_name")
        rec = {"path": rel, "sha256": sha256(path), "bytes": path.stat().st_size,
               "text_chars": len(text), "reasons": sorted(set(reasons))}
        records.append(rec)
        if reasons:
            blocked.append(rec)
    # Scripts and hooks are not published, but they may be auto-committed.
    # Check them for actual credentials without applying personnel-name rules
    # to the scanner's own rule definitions.
    for base in (ROOT / "scripts", ROOT / ".githooks"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            reasons = [f"possible_secret_rule_{i}" for i, r in enumerate(SECRET_RES) if r.search(text)]
            if reasons:
                blocked.append({"path": rel, "reasons": reasons})
    report = {"status": "fail" if blocked else "pass", "file_count": len(records),
              "blocked": blocked, "files": records,
              "checked_at": datetime.now(timezone.utc).isoformat()}
    save_json(STATE / "safety-report.json", report)
    return report


def git_sync():
    paths = [".gitignore", ".okignore", ".githooks", "scripts", "README.md", "AGENTS.md", *PUBLISH_ROOTS]
    # Git keeps reviewed Office/PDF originals; OpenViking indexes their Markdown semantics.
    add = run(["git", "add", "--", *paths])
    if add.returncode:
        raise RuntimeError("git add: " + add.stderr.strip())
    staged = run(["git", "diff", "--cached", "--quiet"])
    if staged.returncode == 1:
        msg = "docs: sync online knowledge " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit = run(["git", "commit", "-m", msg], timeout=180)
        if commit.returncode:
            raise RuntimeError("git commit: " + commit.stderr.strip())
    elif staged.returncode != 0:
        raise RuntimeError("git diff --cached: " + staged.stderr.strip())
    fetch = run(["git", "fetch", "origin", "main"], timeout=180)
    if fetch.returncode:
        raise RuntimeError("git fetch: " + fetch.stderr.strip())
    counts = run(["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"])
    ahead, behind = (int(x) for x in counts.stdout.split())
    if behind:
        if run(["git", "status", "--porcelain"]).stdout.strip():
            raise RuntimeError("remote is ahead and working tree is dirty; manual rebase required")
        rebase = run(["git", "rebase", "origin/main"], timeout=180)
        if rebase.returncode:
            raise RuntimeError("git rebase: " + rebase.stderr.strip())
    push = run(["git", "push", "origin", "main"], timeout=180)
    push_note = None
    if push.returncode:
        # OpenKnowledge autoSync can push the very same local commit while this
        # command is in flight. Accept only an exact remote==HEAD readback;
        # any genuinely different remote history still requires manual review.
        head_after_push = run(["git", "rev-parse", "HEAD"]).stdout.strip()
        remote_after_push = run(["git", "ls-remote", "origin", "refs/heads/main"], timeout=60).stdout.split()
        if not remote_after_push or remote_after_push[0] != head_after_push:
            raise RuntimeError("git push: " + push.stderr.strip())
        push_note = "remote_already_contains_head_after_concurrent_push"
    head = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    remote = run(["git", "ls-remote", "origin", "refs/heads/main"], timeout=60).stdout.split()[0]
    if head != remote:
        raise RuntimeError("origin/main readback does not equal HEAD")
    result = {"commit": head, "remote_verified": True}
    if push_note:
        result["push_note"] = push_note
    return result


def root_inventory(name):
    base = ROOT / name
    paths = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
    files = {p.relative_to(ROOT).as_posix(): sha256(p) for p in paths}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"digest": digest, "files": files}


def wait_task(task_id, raw_dir):
    deadline = time.monotonic() + 2400
    last = {}
    while time.monotonic() < deadline:
        proc = run(["ov", "task", "status", task_id, "-o", "json"], timeout=60)
        if proc.returncode == 0:
            try:
                payload = json.loads(proc.stdout)
                last = payload.get("result") or {}
                save_json(raw_dir / ("task-" + task_id + ".json"), payload)
                status = last.get("status")
                if status == "completed":
                    result = last.get("result") or {}
                    failures = (result.get("errors") or []) + (result.get("failed_files") or [])
                    if result.get("status") == "success" and not failures:
                        return {"task_id": task_id, "status": "completed",
                                "root_uri": result.get("root_uri"),
                                "queue_status": result.get("queue_status")}
                    raise RuntimeError("OpenViking task completed with failures: " + repr(failures))
                if status in {"failed", "cancelled", "canceled"}:
                    raise RuntimeError("OpenViking task " + str(status) + ": " + str(last.get("error")))
            except json.JSONDecodeError:
                pass
        time.sleep(5)
    raise RuntimeError("OpenViking task did not finish within 2400 seconds: " + task_id)


def upload_root(name, inventory, raw_dir):
    source = ROOT / name
    target_name = source.relative_to(ROOT).with_suffix("").as_posix()
    target_uri = CLOUD_PARENT + "/" + target_name
    cmd = ["ov", "add-resource", name, "--to", target_uri,
           "--include", "*.md,*.markdown,*.txt,*.json,*.yaml,*.yml",
           "--ignore-dirs", "node_modules,.git,__pycache__", "--no-progress", "-o", "json"]
    proc = run(cmd, timeout=300)
    save_json(raw_dir / (name.replace("/", "_") + "-submit.json"),
              {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
    if proc.returncode:
        raise RuntimeError("ov add-resource " + name + ": " + (proc.stderr.strip() or proc.stdout.strip()))
    payload = json.loads(proc.stdout)
    if not payload.get("ok"):
        raise RuntimeError("ov add-resource " + name + ": " + repr(payload.get("error")))
    result = payload.get("result") or {}
    task_id = result.get("task_id")
    if not task_id:
        raise RuntimeError("ov add-resource returned no task_id for " + name)
    return wait_task(task_id, raw_dir)


def deleted_paths(previous, current):
    return sorted(set((previous or {}).get("files", {})) - set(current.get("files", {})))


def changed_paths(previous, current):
    old = (previous or {}).get("files", {})
    return sorted(path for path, digest in current.get("files", {}).items()
                  if old.get(path) != digest)


def run_intake_script(script_name, report_name, timeout=900):
    script_args = script_name.split() if isinstance(script_name, str) else list(script_name)
    proc = run([sys.executable, str(ROOT / "scripts" / script_args[0]), *script_args[1:]], timeout=timeout)
    save_json(STATE / report_name, {
        "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr,
    })
    if proc.returncode:
        detail = (proc.stdout.strip() or proc.stderr.strip())[-1500:]
        raise RuntimeError(script_name + " failed: " + detail)
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        raise RuntimeError(script_name + " returned invalid JSON")


def intake_legacy_outputs():
    return run_intake_script("intake_outputs.py", "intake-invocation.json")


def intake_reviewed_sources():
    return run_intake_script("intake_reviewed_sources.py", "reviewed-intake-invocation.json")


def scan_output_ledger():
    return run_intake_script("output_ledger.py --scan".split(), "output-ledger-invocation.json", timeout=1800)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--skip-intake", action="store_true")
    parser.add_argument("--only", action="append", choices=[*PUBLISH_ROOTS, *ROOT_FILES])
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    lock_path = STATE / "sync.lock"
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "skipped", "reason": "another_sync_is_running"}))
            return 0
        intake_summary = None
        reviewed_intake_summary = None
        output_ledger_summary = None
        if not args.check_only and not args.skip_intake:
            try:
                intake_summary = intake_legacy_outputs()
                reviewed_intake_summary = intake_reviewed_sources()
                output_ledger_summary = scan_output_ledger()
            except Exception as e:
                save_json(REPORT_FILE, {"status": "fail", "stage": "intake", "error": str(e)})
                print(json.dumps({"status": "fail", "stage": "intake", "error": str(e)}, ensure_ascii=False))
                return 2
        try:
            preview_summary = ensure_word_previews(check_only=args.check_only)
        except Exception as e:
            save_json(REPORT_FILE, {"status": "fail", "stage": "word_previews", "error": str(e)})
            print(json.dumps({"status": "fail", "stage": "word_previews", "error": str(e)}, ensure_ascii=False))
            return 2
        safety = safety_scan()
        if safety["status"] != "pass":
            save_json(REPORT_FILE, {"status": "blocked", "stage": "safety",
                                    "blocked": safety["blocked"]})
            print(json.dumps({"status": "blocked", "blocked_count": len(safety["blocked"]),
                              "report": str(STATE / "safety-report.json")}, ensure_ascii=False))
            return 2
        if args.check_only:
            print(json.dumps({"status": "pass", "file_count": safety["file_count"]}))
            return 0
        report = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
                  "intake": intake_summary, "reviewed_intake": reviewed_intake_summary,
                  "output_ledger": output_ledger_summary,
                  "word_previews": preview_summary,
                  "git": None, "uploaded": [], "skipped": [], "errors": []}
        save_json(REPORT_FILE, report)
        try:
            report["git"] = git_sync()
            state = load_state()
            roots = args.only or [*PUBLISH_ROOTS, *ROOT_FILES]
            raw_dir = STATE / "raw" / datetime.now().strftime("%Y%m%dT%H%M%S")
            for name in roots:
                if not (ROOT / name).exists():
                    continue
                if name in PUBLISH_ROOTS and name not in SEARCH_ROOTS:
                    report["skipped"].append({"root": name,
                        "reason": "git_only_originals_semantic_markdown_lives_in_docs"})
                    continue
                current = root_inventory(name)
                previous = (state.get("roots") or {}).get(name)
                if previous and previous.get("digest") == current["digest"]:
                    report["skipped"].append({"root": name, "reason": "unchanged"})
                    continue
                if previous:
                    removed = deleted_paths(previous, current)
                    if removed:
                        report["errors"].append({"root": name,
                            "error": "deletion_requires_manual_review", "paths": removed})
                        continue
                try:
                    if (ROOT / name).is_dir():
                        if not previous:
                            raise RuntimeError("missing_verified_incremental_baseline_for_" + name)
                        changed = changed_paths(previous, current)
                        outcomes = [{"path": rel, **upload_root(rel, current, raw_dir)}
                                    for rel in changed]
                        report["uploaded"].append({"root": name, "file_count": len(outcomes),
                                                  "files": outcomes})
                    else:
                        outcome = upload_root(name, current, raw_dir)
                        report["uploaded"].append({"root": name, **outcome})
                    state.setdefault("roots", {})[name] = current
                    save_json(STATE_FILE, state)
                    save_json(REPORT_FILE, report)
                except Exception as e:
                    report["errors"].append({"root": name, "error": str(e)})
            report["status"] = "pass" if not report["errors"] else "fail"
        except Exception as e:
            report["status"] = "fail"
            report["errors"].append({"stage": "git_or_runtime", "error": str(e)})
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_json(REPORT_FILE, report)
        print(json.dumps({"status": report["status"], "git": report["git"],
                          "uploaded": report["uploaded"], "skipped": report["skipped"],
                          "errors": report["errors"], "report": str(REPORT_FILE)}, ensure_ascii=False))
        return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
