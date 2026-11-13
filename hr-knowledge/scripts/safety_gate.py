#!/usr/bin/env python3
"""Repository pre-commit entry point; performs no network or Git writes."""
import json
import sys
from sync_online import safety_scan

report = safety_scan()
print(json.dumps({"status": report["status"], "file_count": report["file_count"],
                  "blocked": report["blocked"]}, ensure_ascii=False))
sys.exit(0 if report["status"] == "pass" else 2)
