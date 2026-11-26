"""Runtime configuration for the LifeDesk backend.

Provider selection is driven by environment variables so the workflow engine,
API surface and frontend remain unchanged when local providers are swapped for
MCP-backed providers during the hackathon.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

#: SQLite file. Overridable for tests (`LIFEDESK_DB`).
DB_PATH = Path(os.environ.get("LIFEDESK_DB", BACKEND_DIR / "lifedesk.db"))

#: "local" (SQLite providers) or "mcp" (MCP-backed providers).
PROVIDER_MODE = os.environ.get("LIFEDESK_PROVIDER_MODE", "local").strip().lower()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


#: MCP transport: "stdio" (bundled reference server or a command) or "http".
MCP_TRANSPORT = os.environ.get("LIFEDESK_MCP_TRANSPORT", "stdio").strip().lower()
#: stdio server command. Defaults to the interpreter running the backend.
MCP_COMMAND = os.environ.get("LIFEDESK_MCP_COMMAND", "").strip() or sys.executable
#: JSON array of arguments for the stdio command. Defaults to the bundled server.
MCP_ARGS_RAW = os.environ.get("LIFEDESK_MCP_ARGS")
#: Working directory for the stdio server. Defaults to the backend directory.
MCP_CWD = os.environ.get("LIFEDESK_MCP_CWD", "").strip()
#: Streamable HTTP endpoint for an external MCP bridge.
MCP_URL = os.environ.get("LIFEDESK_MCP_URL", "").strip()
#: JSON object of headers (for example a bearer token) sent to an HTTP MCP server.
MCP_HEADERS_RAW = os.environ.get("LIFEDESK_MCP_HEADERS")
#: JSON object of extra environment variables passed to a stdio MCP server.
MCP_ENV_RAW = os.environ.get("LIFEDESK_MCP_ENV")
#: Human-readable server label used in status output (never include credentials here).
MCP_LABEL = os.environ.get("LIFEDESK_MCP_LABEL", "").strip()
#: Seconds allowed for one MCP handshake/tool call.
MCP_TIMEOUT = _env_float("LIFEDESK_MCP_TIMEOUT", 15.0)
#: "local" falls back to SQLite when MCP startup fails; "error" fails startup.
MCP_FALLBACK = os.environ.get("LIFEDESK_MCP_FALLBACK", "local").strip().lower()

#: CORS origins allowed for the Vite dev server.
CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
]

#: Seed demo content on first start only.
SEED_DEMO_DATA = os.environ.get("LIFEDESK_SEED", "1") != "0"

APP_NAME = "LifeDesk"
APP_VERSION = "0.9.0-demo"
