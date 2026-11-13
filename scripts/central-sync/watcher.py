#!/usr/bin/env python3
import json, os, shutil, signal, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("DSH_CENTRAL_STATE", str(Path.home() / ".dsh" / "state" / "dsh-central-sync"))).resolve()
STATE.mkdir(parents=True, exist_ok=True)
ROOTS = [Path(p) for p in os.environ.get(
    "DSH_CENTRAL_WATCH_ROOTS",
    "/Users/leto/.dsh/bot/workspace:/Users/leto/WorkBuddy/HR技术中台/hr-knowledge",
).split(":") if p]

def now():
    return datetime.now(timezone.utc).isoformat()

def status(mode, **extra):
    value = {"mode": mode, "updated_at": now(), **extra}
    (STATE / "watcher-status.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def trigger(mode):
    proc = subprocess.run([sys.executable, str(SCRIPT / "run_once.py")], capture_output=True, text=True, timeout=1800)
    status(mode, last_trigger_at=now(), last_returncode=proc.returncode, last_output=proc.stdout[-1000:], last_error=proc.stderr[-1000:])

def main():
    fswatch = shutil.which("fswatch")
    if not fswatch:
        status("poll_fallback", interval_seconds=60)
        while True:
            trigger("poll_fallback")
            time.sleep(60)
    cmd = [fswatch, "-0", "-r", "--latency=30", "-e", "/[.]git/", "-e", "/node_modules/",
           "-e", "/__pycache__/", "-e", "[.]pyc$", *[str(p) for p in ROOTS if p.is_dir()]]
    status("fswatch", latency_seconds=30)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        trigger("startup")
        while True:
            data = os.read(proc.stdout.fileno(), 65536)
            if not data:
                error = proc.stderr.read().decode("utf-8", errors="replace")[-1000:]
                status("fswatch_stopped", returncode=proc.wait(), error=error)
                return 2
            trigger("fswatch")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

if __name__ == "__main__":
    raise SystemExit(main())
