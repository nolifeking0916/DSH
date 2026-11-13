#!/usr/bin/env python3
import json, os, shutil, subprocess, sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "project_knowledge.py"
BASE = Path("/Users/leto/.dsh/state/dsh-central-sync/knowledge-projection-tests")


def run(source, root, state, apply=True):
    env = dict(os.environ, DSH_CENTRAL_KNOWLEDGE_SOURCE=str(source),
               DSH_CENTRAL_ROOT=str(root), DSH_CENTRAL_STATE=str(state))
    args = [sys.executable, str(SCRIPT)] + (["--apply"] if apply else [])
    proc = subprocess.run(args, env=env, capture_output=True, text=True, timeout=120)
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        raise AssertionError((proc.returncode, proc.stdout, proc.stderr))
    return proc.returncode, payload


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    if BASE.exists():
        shutil.rmtree(BASE)
    source = BASE / "basic" / "source"
    root = BASE / "basic" / "root"
    state = BASE / "basic" / "state"
    original = source / "docs" / "sample.md"
    write(original, "synthetic knowledge v1\n")
    # Same-content central files may be adopted without a prior local manifest.
    write(root / "hr-knowledge" / "docs" / "sample.md", "synthetic knowledge v1\n")
    code, out = run(source, root, state)
    assert code == 0 and out["file_count"] == 1, out
    write(original, "synthetic knowledge v2\n")
    code, out = run(source, root, state)
    assert code == 0 and (root / "hr-knowledge" / "docs" / "sample.md").read_text() == "synthetic knowledge v2\n", out
    renamed = source / "docs" / "renamed.md"
    os.replace(original, renamed)
    code, out = run(source, root, state)
    assert code == 0 and out["rename_count"] == 1, out
    assert not (root / "hr-knowledge" / "docs" / "sample.md").exists()
    assert (root / "hr-knowledge" / "docs" / "renamed.md").exists()
    renamed.unlink()
    code, out = run(source, root, state)
    assert code == 2 and out["deletion_count"] == 1, out
    assert (root / "hr-knowledge" / "docs" / "renamed.md").exists(), "delete hold must preserve central copy"

    sensitive_source = BASE / "sensitive" / "source"
    sensitive_root = BASE / "sensitive" / "root"
    sensitive_state = BASE / "sensitive" / "state"
    write(sensitive_source / "docs" / "blocked.md",
          "synthetic placeholder\n-----BE" + "GIN " + "OPENSSH PRIVATE KEY-----\nnot-a-real-key\n")
    code, out = run(sensitive_source, sensitive_root, sensitive_state)
    assert code == 2 and not (sensitive_root / "hr-knowledge" / "docs" / "blocked.md").exists(), out

    conflict_source = BASE / "conflict" / "source"
    conflict_root = BASE / "conflict" / "root"
    conflict_state = BASE / "conflict" / "state"
    write(conflict_source / "docs" / "same.md", "source synthetic\n")
    write(conflict_root / "hr-knowledge" / "docs" / "same.md", "different central content\n")
    code, out = run(conflict_source, conflict_root, conflict_state)
    assert code == 2, out
    assert (conflict_root / "hr-knowledge" / "docs" / "same.md").read_text() == "different central content\n"
    report = json.loads((conflict_state / "knowledge-projection-report.json").read_text())
    assert any("existing_target_identity_mismatch" in x.get("reasons", []) for x in report["errors"]), report

    result = {"status": "pass", "cases": ["adopt_same_hash", "modify", "rename", "delete_hold",
              "sensitive_blocked_before_copy", "existing_identity_conflict_hold"]}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
