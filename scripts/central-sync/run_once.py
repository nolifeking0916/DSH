#!/usr/bin/env python3
import fcntl, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("DSH_CENTRAL_STATE", str(Path.home() / ".dsh" / "state" / "dsh-central-sync"))).resolve()
SCANNER = Path(os.environ.get("DSH_CENTRAL_LEDGER_SCANNER", "/Users/leto/WorkBuddy/HR技术中台/hr-knowledge/scripts/output_ledger.py")).resolve()
STATE.mkdir(parents=True, exist_ok=True)


def invoke(script, *args):
    path = Path(script)
    if not path.is_absolute():
        path = SCRIPT / path
    proc = subprocess.run([sys.executable, str(path), *args], capture_output=True, text=True, timeout=1800)
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except Exception:
        payload = {}
    return {"returncode": proc.returncode, "payload": payload,
            "stderr_tail": proc.stderr[-1000:], "stdout_tail": proc.stdout[-1000:] if not payload else ""}


def main():
    with (STATE / "run-once.lock").open("w") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "already_running"}))
            return 0
        started = datetime.now(timezone.utc).isoformat()
        scan = invoke(str(SCANNER), "--scan")
        scan_status = scan["payload"].get("status")
        scan_ok = scan["returncode"] == 0 and scan_status == "pass"
        knowledge = {"returncode": 0, "payload": {"status": "skipped"}}
        outputs = {"returncode": 0, "payload": {"status": "skipped"}}
        sync = None
        if scan_ok:
            knowledge = invoke("project_knowledge.py", "--apply")
        if scan_ok and knowledge["returncode"] == 0:
            outputs = invoke("project_outputs.py", "--apply")
        if scan_ok and knowledge["returncode"] == 0 and outputs["returncode"] == 0:
            sync = invoke("sync_online.py", "--git-only")
        code = 0 if scan_ok else (scan["returncode"] or 2)
        code = code or knowledge["returncode"] or outputs["returncode"] or (sync or {}).get("returncode", 0)
        result = {
            "started_at": started,
            "ledger_scan": scan,
            "knowledge_projection": knowledge,
            "output_projection": outputs,
            "sync": sync,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "pass" if code == 0 else "held",
        }
        (STATE / "run-once-last.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": result["status"],
            "ledger_scan": scan["payload"],
            "knowledge_projection": knowledge["payload"],
            "output_projection": outputs["payload"],
            "sync": (sync or {}).get("payload"),
            "report": str(STATE / "run-once-last.json"),
        }, ensure_ascii=False))
        return code


if __name__ == "__main__":
    raise SystemExit(main())
