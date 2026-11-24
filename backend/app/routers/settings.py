from fastapi import APIRouter, HTTPException

from ..config import APP_NAME, APP_VERSION
from ..providers.registry import get_services
from ..services.ai import ai_status
from ..services.settings import SettingsUpdate, get_settings, update_settings

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def read_settings():
    return get_settings()


@router.put("/settings")
def save_settings(payload: SettingsUpdate):
    return update_settings(payload)


@router.get("/system")
def system_status():
    services = get_services()
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "demo_mode": True,
        "demo_label": "Demo Mode — Local Data",
        "provider_mode": services.mode,
        "providers": services.provider_infos(),
        "ai": ai_status(),
        "storage": {
            "engine": "SQLite",
            "persistent": True,
            "note": "All edits persist to backend/lifedesk.db across restarts.",
        },
        "integrations": [
            {
                "name": "MCP servers",
                "status": "not_configured",
                "detail": "Provider interfaces + adapter boundary ready; connection happens during the hackathon.",
            },
            {
                "name": "Calendar OAuth",
                "status": "not_configured",
                "detail": "Local calendar provider active. Google/Outlook sync is out of scope for the prototype.",
            },
            {
                "name": "LLM provider",
                "status": "not_configured",
                "detail": "Deterministic interpreter active. No paid API key required.",
            },
        ],
    }
