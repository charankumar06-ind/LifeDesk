"""Runtime configuration for the LifeDesk backend.

Provider selection is driven by environment variables so the workflow engine,
API surface and frontend remain unchanged when local providers are swapped for
MCP-backed providers during the hackathon.
"""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

#: SQLite file. Overridable for tests (`LIFEDESK_DB`).
DB_PATH = Path(os.environ.get("LIFEDESK_DB", BACKEND_DIR / "lifedesk.db"))

#: "local" (SQLite providers) or "mcp" (future MCP providers).
PROVIDER_MODE = os.environ.get("LIFEDESK_PROVIDER_MODE", "local").strip().lower()

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
