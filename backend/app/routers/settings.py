from fastapi import APIRouter, HTTPException

from ..config import APP_NAME, APP_VERSION, MCP_FALLBACK, MCP_TRANSPORT, PROVIDER_MODE
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
    runtime = services.runtime or {}
    mode = services.mode
    mcp_degraded = mode == "mcp" and runtime.get("status") == "error"

    if mcp_degraded:
        mcp_integration_status = "error"
        mcp_detail = (
            "An MCP call failed, so the provider is degraded. No local fallback was used: "
            "writes return 503 until a later call succeeds. Last error: "
            f"{runtime.get('error') or 'unknown error'}"
        )
    elif mode == "mcp":
        mcp_integration_status = "connected"
        mcp_detail = (
            f"Connected over {runtime.get('transport', 'mcp')} to "
            f"{runtime.get('endpoint', 'the configured MCP server')}. "
            f"{len(runtime.get('tools', []))} tools discovered."
        )
    elif mode == "local-fallback":
        mcp_integration_status = "fallback"
        mcp_detail = (
            "MCP startup failed, so local SQLite providers are active. "
            "No workflow writes were routed to MCP. Fix the server and restart the backend."
        )
    else:
        mcp_integration_status = "not_configured"
        mcp_detail = (
            "Local providers active. Set LIFEDESK_PROVIDER_MODE=mcp to use the bundled "
            "reference server or a compatible external MCP server."
        )

    if mcp_degraded:
        demo_label = "MCP Degraded — Calls Failing"
        storage_engine = "MCP server"
        storage_note = (
            "The last MCP call failed. Writes are not redirected to SQLite; they return "
            "HTTP 503 until the MCP server answers again."
        )
    elif mode == "mcp":
        demo_label = "MCP Mode — Reference/External Server"
        storage_engine = "MCP server"
        storage_note = (
            "Writes go through the configured MCP server. The bundled reference server "
            "stores them in backend/lifedesk.db; external servers keep their own storage."
        )
    elif mode == "local-fallback":
        demo_label = "MCP Fallback — Local Data"
        storage_engine = "SQLite"
        storage_note = (
            "MCP was unavailable at startup, so all reads and writes use backend/lifedesk.db."
        )
    else:
        demo_label = "Demo Mode — Local Data"
        storage_engine = "SQLite"
        storage_note = "All edits persist to backend/lifedesk.db across restarts."

    mail_available = bool(runtime.get("mail_available"))
    if mode == "mcp" and not mail_available:
        mail_integration_status = "not_configured"
        mail_detail = (
            "The MCP server connected but does not expose the optional mail_send tool. "
            "Email is unavailable; calendar, task and reminder calls keep working."
        )
    elif mode == "mcp" and runtime.get("mail_configured") is True:
        mail_integration_status = "connected"
        mail_detail = (
            "SMTP delivery is configured on the MCP server. Email is sent only after "
            "you approve and execute the workflow."
        )
    elif mode == "mcp":
        mail_integration_status = "not_configured"
        mail_detail = (
            "The MCP mail tool is connected but SMTP credentials are missing or unreported. "
            "Set LIFEDESK_SMTP_USER and LIFEDESK_SMTP_PASSWORD for the MCP server and restart it."
        )
    elif mode == "local-fallback":
        mail_integration_status = "not_configured"
        mail_detail = (
            "Local fallback providers are active, so email is not sent. Restore MCP mode to "
            "use the server's mail tool."
        )
    else:
        mail_integration_status = "not_configured"
        mail_detail = (
            "Local mode does not deliver email. Switch LIFEDESK_PROVIDER_MODE to mcp and "
            "configure SMTP on the MCP server to send mail."
        )

    mcp = {
        "requested": PROVIDER_MODE == "mcp",
        "configured": bool(runtime.get("configured")),
        "transport": runtime.get("transport", MCP_TRANSPORT),
        "endpoint": runtime.get("endpoint", ""),
        "status": runtime.get("status", "not_requested"),
        "fallback_active": mode == "local-fallback",
        "fallback_mode": MCP_FALLBACK,
        "error": runtime.get("error"),
        "tools": runtime.get("tools", []),
        "required_tools": runtime.get("required_tools", []),
        "mail_available": mail_available,
        "mail_configured": runtime.get("mail_configured"),
        "checked_at": runtime.get("checked_at"),
    }

    providers = services.provider_infos()
    if mcp_degraded:
        error_text = runtime.get("error") or "The last MCP call failed."
        providers = [
            {
                **provider,
                "status": "error",
                "note": (
                    f"Degraded: {error_text} No local fallback is active; the next "
                    "successful call restores this provider."
                ),
            }
            if provider.get("kind") == "mcp"
            else provider
            for provider in providers
        ]

    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "demo_mode": mode != "mcp",
        "demo_label": demo_label,
        "provider_mode": mode,
        "providers": providers,
        "mcp": mcp,
        "ai": ai_status(),
        "storage": {
            "engine": storage_engine,
            "persistent": True,
            "note": storage_note,
        },
        "integrations": [
            {
                "name": "MCP servers",
                "status": mcp_integration_status,
                "detail": mcp_detail,
            },
            {
                "name": "Email (SMTP)",
                "status": mail_integration_status,
                "detail": mail_detail,
            },
            {
                "name": "Calendar OAuth",
                "status": "not_configured",
                "detail": (
                    "OAuth is owned by the MCP server. The bundled reference server needs no "
                    "credentials; an external Google/Outlook bridge must manage its own OAuth."
                ),
            },
            {
                "name": "LLM provider",
                "status": "not_configured",
                "detail": "Deterministic interpreter active. No paid API key required.",
            },
        ],
    }
