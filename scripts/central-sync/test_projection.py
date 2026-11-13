#!/usr/bin/env python3
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "project_outputs.py"
BASE = Path("/Users/leto/.dsh/state/dsh-central-sync/projection-test")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(env):
    p = subprocess.run([sys.executable, str(SCRIPT), "--apply"], env=env, capture_output=True, text=True)
    return p.returncode, json.loads(p.stdout)

def main():
    if BASE.exists():
        shutil.rmtree(BASE)
    source = BASE / "source"
    root = BASE / "repo"
    state = BASE / "state"
    source.mkdir(parents=True)
    report = BASE / "report.json"
    env = dict(os.environ, DSH_OUTPUT_WORKSPACE=str(source), DSH_CENTRAL_ROOT=str(root),
               DSH_CENTRAL_STATE=str(state), DSH_OUTPUT_LEDGER_REPORT=str(report))
    def write_record(path, artifact="artifact-1"):
        value = {"artifact_id": artifact, "path": str(path), "sha256": digest(path),
                 "status": "eligible_reviewed_intake", "origin_confidence": "confirmed"}
        report.write_text(json.dumps({"records": [value]}), encoding="utf-8")
    first = source / "first.md"
    first.write_text("synthetic v1\n", encoding="utf-8")
    write_record(first)
    code, out = run(env)
    assert code == 0 and out["file_count"] == 1, out
    target = root / "dsh-workspace" / "first.md"
    assert target.read_text(encoding="utf-8") == "synthetic v1\n"
    first.write_text("synthetic v2\n", encoding="utf-8")
    write_record(first)
    code, out = run(env)
    assert code == 0 and target.read_text(encoding="utf-8") == "synthetic v2\n", out
    renamed = source / "renamed.md"
    os.replace(first, renamed)
    write_record(renamed)
    code, out = run(env)
    assert code == 0 and out["rename_count"] == 1, out
    assert not target.exists() and (root / "dsh-workspace" / "renamed.md").exists()
    report.write_text(json.dumps({"records": []}), encoding="utf-8")
    code, out = run(env)
    assert code == 2 and out["deletion_count"] == 1, out
    assert (root / "dsh-workspace" / "renamed.md").exists(), "deletion hold must not remove staged file"
    # Same target + same SHA is safe to adopt even if the ledger artifact id changed.
    write_record(renamed, artifact="different-artifact")
    code, out = run(env)
    assert code == 0 and out["error_count"] == 0, out
    # Atomic replacement may change the inode/artifact id; a unique previous target
    # still proves lineage, so this is a modification rather than an unknown collision.
    renamed.write_text("synthetic atomic-replacement v3\n", encoding="utf-8")
    write_record(renamed, artifact="third-artifact")
    code, out = run(env)
    assert code == 0 and out["error_count"] == 0, out
    assert (root / "dsh-workspace" / "renamed.md").read_text(encoding="utf-8") == "synthetic atomic-replacement v3\n"
    # A reviewed exclusion removes the candidate without deleting the central copy or
    # misclassifying the explicit scope decision as a source deletion.
    state.mkdir(parents=True, exist_ok=True)
    (state / "excluded-targets.json").write_text(json.dumps({"excluded": [{"target": "dsh-workspace/renamed.md", "sha256": digest(renamed), "reason": "synthetic_sensitive"}]}), encoding="utf-8")
    code, out = run(env)
    assert code == 0 and out["file_count"] == 0 and out["deletion_count"] == 0, out
    assert (root / "dsh-workspace" / "renamed.md").exists(), "exclusion must preserve the central copy"
    # A target with no manifest lineage remains blocked even when the new source is valid.
    unknown = source / "unknown.md"
    unknown.write_text("new source\n", encoding="utf-8")
    unknown_target = root / "dsh-workspace" / "unknown.md"
    unknown_target.write_text("unowned existing target\n", encoding="utf-8")
    write_record(unknown, artifact="unknown-artifact")
    code, out = run(env)
    assert code == 2 and out["error_count"] >= 1, out
    assert unknown_target.read_text(encoding="utf-8") == "unowned existing target\n"
    print(json.dumps({"status": "pass", "cases": ["initial", "modify", "rename", "delete_hold", "same_hash_adoption", "atomic_replace_same_target_modify", "explicit_exclusion_preserve", "unknown_target_identity_conflict_hold"]}))

if __name__ == "__main__":
    main()
