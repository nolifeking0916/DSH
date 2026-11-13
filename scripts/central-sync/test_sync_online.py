#!/usr/bin/env python3
import json, os, shutil, subprocess, sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent
BASE = Path("/Users/leto/.dsh/state/dsh-central-sync/synthetic-sync-tests")

def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

def setup(name):
    root = BASE / name / "root"
    bare = BASE / name / "remote.git"
    root.mkdir(parents=True)
    subprocess.check_call(["git", "init", "--bare", "-b", "main", str(bare)], stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "init", "-b", "main", str(root)], stdout=subprocess.DEVNULL)
    git(root, "config", "user.name", "DSH Synthetic Test")
    git(root, "config", "user.email", "noreply@example.invalid")
    git(root, "remote", "add", "origin", str(bare))
    (root / "dsh-workspace").mkdir()
    (root / "dsh-workspace" / "sample.md").write_text("synthetic public content\n", encoding="utf-8")
    return root, bare, BASE / name / "state"

def sync(root, state):
    env = dict(os.environ, DSH_CENTRAL_ROOT=str(root), DSH_CENTRAL_STATE=str(state))
    p = subprocess.run([sys.executable, str(SCRIPT / "sync_online.py"), "--git-only"], env=env, capture_output=True, text=True, timeout=120)
    payload = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
    return p.returncode, payload

def main():
    if BASE.exists():
        shutil.rmtree(BASE)
    BASE.mkdir(parents=True)
    results = {}
    root, bare, state = setup("recovery")
    missing = BASE / "recovery" / "missing.git"
    git(root, "remote", "set-url", "origin", str(missing))
    code, out = sync(root, state)
    assert code != 0 and out["status"] == "fail", out
    first_commit = git(root, "rev-parse", "HEAD")
    git(root, "remote", "set-url", "origin", str(bare))
    code, out = sync(root, state)
    assert code == 0 and out["git"]["remote_verified"] is True, out
    assert git(root, "rev-parse", "HEAD") == first_commit == git(bare, "rev-parse", "main")
    results["push_failure_recovery_without_new_change"] = "pass"

    other = BASE / "recovery" / "other"
    subprocess.check_call(["git", "clone", str(bare), str(other)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git(other, "config", "user.name", "Other Synthetic Writer")
    git(other, "config", "user.email", "other@example.invalid")
    (other / "remote-change.md").write_text("remote synthetic change\n", encoding="utf-8")
    git(other, "add", "remote-change.md")
    git(other, "commit", "-m", "synthetic remote change")
    remote_head = git(other, "rev-parse", "HEAD")
    git(other, "push", "origin", "main")
    (root / "dsh-workspace" / "sample.md").write_text("local synthetic edit\n", encoding="utf-8")
    code, out = sync(root, state)
    assert code != 0 and any("remote_ahead_manual_review_required" in x.get("error", "") for x in out.get("errors", [])), out
    assert git(bare, "rev-parse", "main") == remote_head
    results["remote_ahead_no_rebase_no_force"] = "pass"

    root2, bare2, state2 = setup("deletion")
    code, out = sync(root2, state2)
    assert code == 0, out
    remote_head2 = git(bare2, "rev-parse", "main")
    (root2 / "dsh-workspace" / "sample.md").unlink()
    code, out = sync(root2, state2)
    assert code != 0 and any("deletion_requires_manual_review" in x.get("error", "") for x in out.get("errors", [])), out
    assert git(bare2, "rev-parse", "main") == remote_head2
    results["staged_deletion_blocked"] = "pass"

    sensitive_root = BASE / "sensitive" / "root"
    sensitive_state = BASE / "sensitive" / "state"
    sensitive_root.mkdir(parents=True)
    (sensitive_root / "dsh-workspace").mkdir()
    (sensitive_root / "dsh-workspace" / "blocked.md").write_text("synthetic placeholder\n-----BE" + "GIN " + "OPENSSH PRIVATE KEY-----\nnot-a-real-key\n", encoding="utf-8")
    env = dict(os.environ, DSH_CENTRAL_ROOT=str(sensitive_root), DSH_CENTRAL_STATE=str(sensitive_state))
    p = subprocess.run([sys.executable, str(SCRIPT / "sync_online.py"), "--check-only", "--git-only"], env=env, capture_output=True, text=True)
    out = json.loads(p.stdout)
    assert p.returncode == 2 and out["blocked_count"] >= 1, out
    assert not (sensitive_root / ".git").exists()
    results["sensitive_blocked_before_git"] = "pass"
    report = {"status": "pass", "cases": results}
    (BASE.parent / "synthetic-test-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))

if __name__ == "__main__":
    main()
