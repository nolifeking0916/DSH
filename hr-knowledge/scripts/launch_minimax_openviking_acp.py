#!/usr/bin/env python3
"""Launch Claude ACP with existing MiniMax and OpenViking credentials.

Secrets are read from the current user configuration and exported only to the
child process. They are never written to this repository or printed to stdout,
which belongs to the ACP JSON-RPC transport.
"""

import json
import os
from pathlib import Path
import sys

HOME = Path.home()
MINIMAX_REFS = HOME / ".dsh" / ".credentials.yaml"
OPENVIKING_CONFIG = HOME / ".openviking" / "ovcli.conf"
ACP_BINARY = Path("/opt/homebrew/bin/claude-agent-acp")
MODEL = "MiniMax-M3.1-Flash"
MINIMAX_BASE_URL = "https://api.minimaxi.com/anthropic"


def read_minimax_key(path: Path = MINIMAX_REFS) -> str:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("MINIMAX_CN_API_KEY:"):
            continue
        value = line.split(":", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if not value or value.startswith(("file:", "env:", "secret:", "ref:")):
            raise RuntimeError("MINIMAX_CN_API_KEY is not a directly usable key")
        return value
    raise RuntimeError("MINIMAX_CN_API_KEY was not found")


def read_openviking_config(path: Path = OPENVIKING_CONFIG) -> tuple[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    base_url = str(data["url"]).rstrip("/")
    api_key = str(data["api_key"])
    if not base_url.startswith("https://") or not api_key or set(api_key) == {"*"}:
        raise RuntimeError("OpenViking URL or API key is invalid")
    return base_url, api_key


def child_environment() -> dict[str, str]:
    minimax_key = read_minimax_key()
    ov_base_url, ov_api_key = read_openviking_config()
    env = os.environ.copy()
    env.update(
        {
            "ANTHROPIC_BASE_URL": MINIMAX_BASE_URL,
            "ANTHROPIC_AUTH_TOKEN": minimax_key,
            "ANTHROPIC_API_KEY": minimax_key,
            "ANTHROPIC_MODEL": MODEL,
            "ANTHROPIC_SMALL_FAST_MODEL": MODEL,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": MODEL,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": MODEL,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": MODEL,
            "OPENVIKING_MCP_URL": ov_base_url + "/mcp",
            "OPENVIKING_API_KEY": ov_api_key,
            "API_TIMEOUT_MS": "300000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1",
        }
    )
    return env


def main() -> None:
    if not ACP_BINARY.is_file():
        raise RuntimeError(f"ACP adapter is missing: {ACP_BINARY}")
    if "--check" in sys.argv:
        env = child_environment()
        print(
            json.dumps(
                {
                    "status": "pass",
                    "adapter": str(ACP_BINARY),
                    "model": env["ANTHROPIC_MODEL"],
                    "minimax_base_url": env["ANTHROPIC_BASE_URL"],
                    "openviking_mcp_url": env["OPENVIKING_MCP_URL"],
                    "minimax_key_loaded": bool(env["ANTHROPIC_AUTH_TOKEN"]),
                    "openviking_key_loaded": bool(env["OPENVIKING_API_KEY"]),
                },
                ensure_ascii=False,
            )
        )
        return
    os.execvpe(str(ACP_BINARY), [str(ACP_BINARY)], child_environment())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"HR MiniMax/OpenViking launcher: {exc}", file=sys.stderr)
        raise SystemExit(1)
