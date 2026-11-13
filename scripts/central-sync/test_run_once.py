#!/usr/bin/env python3
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

BASE = Path("/Users/leto/.dsh/state/dsh-central-sync/run-once-tests")
SCRIPT = Path(__file__).resolve().parent


def git(cwd, *args):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def main():
    if BASE.exists():
        shutil.rmtree(BASE)
    root = BASE / "root"
    bare = BASE / "remote.git"
    state = BASE / "state"
    source = BASE / "knowledge"
    workspace = BASE / "workspace"
    root.mkdir(parents=True)
    git(BASE, "init", "--bare", "--initial-branch=main", str(bare))
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Synthetic Test")
    git(root, "config", "user.email", "synthetic@example.invalid")
    (root / "README.md").write_text("synthetic central\n", encoding="utf-8")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "initial")
    git(root, "remote", "add", "origin", str(bare))
    git(root, "push", "-u", "origin", "main")

    knowledge_file = source / "docs" / "knowledge.md"
    knowledge_file.parent.mkdir(parents=True)
    knowledge_file.write_text("synthetic central knowledge\n", encoding="utf-8")
    output_file = workspace / "outputs" / "result.md"
    output_file.parent.mkdir(parents=True)
    output_file.write_text("synthetic DSH output\n", encoding="utf-8")
    digest = hashlib.sha256(output_file.read_bytes()).hexdigest()
    report = BASE / "ledger.json"
    report.write_text(json.dumps({"records": [{
        "status": "eligible_reviewed_intake", "origin_confidence": "confirmed",
        "artifact_id": "synthetic-artifact", "sha256": digest,
        "path": str(output_file), "source_root": str(workspace),
    }]}), encoding="utf-8")
    scanner = BASE / "scanner.py"
    scanner.write_text("import json; print(json.dumps({'status':'pass','errors':0}))\n", encoding="utf-8")
    env = dict(os.environ,
        DSH_CENTRAL_ROOT=str(root), DSH_CENTRAL_STATE=str(state),
        DSH_CENTRAL_KNOWLEDGE_SOURCE=str(source), DSH_CENTRAL_LEDGER_SCANNER=str(scanner),
        DSH_OUTPUT_WORKSPACE=str(workspace), DSH_OUTPUT_LEDGER_REPORT=str(report))

    def run_once():
        proc = subprocess.run([sys.executable, str(SCRIPT / "run_once.py")], env=env,
                              capture_output=True, text=True, timeout=180)
        return proc.returncode, json.loads(proc.stdout)

    code, out = run_once()
    assert code == 0 and out["status"] == "pass", out
    first_head = git(bare, "rev-parse", "main")
    assert git(bare, "show", "main:hr-knowledge/docs/knowledge.md") == "synthetic central knowledge"
    assert git(bare, "show", "main:dsh-workspace/outputs/result.md") == "synthetic DSH output"

    scanner.write_text("import json; print(json.dumps({'status':'skipped','reason':'test_lock'}))\n", encoding="utf-8")
    code, out = run_once()
    assert code != 0 and out["status"] == "held", out
    assert git(bare, "rev-parse", "main") == first_head

    scanner.write_text("import json; print(json.dumps({'status':'pass','errors':0}))\n", encoding="utf-8")
    knowledge_file.unlink()
    code, out = run_once()
    assert code != 0 and out["status"] == "held", out
    assert git(bare, "rev-parse", "main") == first_head
    assert (root / "hr-knowledge" / "docs" / "knowledge.md").exists()

    print(json.dumps({"status": "pass", "cases": [
        "scan_then_knowledge_then_outputs_then_git",
        "scanner_lock_skips_all_stages",
        "knowledge_delete_holds_before_git",
        "remote_content_readback",
    ]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
