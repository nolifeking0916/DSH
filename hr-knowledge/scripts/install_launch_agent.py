#!/usr/bin/env python3
"""Install the per-user five-minute sync LaunchAgent; no secrets are stored."""
from pathlib import Path
import plistlib
import subprocess

home = Path.home()
root = Path(__file__).resolve().parents[1]
target = home / "Library" / "LaunchAgents" / "com.uu1.hr-knowledge-sync.plist"
logs = home / "Library" / "Logs" / "hr-knowledge-sync"
logs.mkdir(parents=True, exist_ok=True)
target.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "Label": "com.uu1.hr-knowledge-sync",
    "ProgramArguments": [
        "/Users/leto/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3",
        str(root / "scripts" / "sync_online.py"),
    ],
    "WorkingDirectory": str(root),
    "EnvironmentVariables": {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(home),
        "LANG": "en_US.UTF-8",
    },
    "StartInterval": 300,
    "RunAtLoad": True,
    "ThrottleInterval": 60,
    "Nice": 10,
    "LowPriorityIO": True,
    "StandardOutPath": str(logs / "stdout.log"),
    "StandardErrorPath": str(logs / "stderr.log"),
}
with target.open("wb") as f:
    plistlib.dump(payload, f, sort_keys=False)
subprocess.run(["plutil", "-lint", str(target)], check=True)
uid = subprocess.check_output(["id", "-u"], text=True).strip()
service = "gui/" + uid + "/com.uu1.hr-knowledge-sync"
subprocess.run(["launchctl", "bootout", service], capture_output=True)
subprocess.run(["launchctl", "bootstrap", "gui/" + uid, str(target)], check=True)
subprocess.run(["launchctl", "enable", service], check=True)
print(target)
print(service)
