from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_NAME, APP_VERSION, BACKEND_DIR, CORS_ORIGINS, PROVIDER_MODE
from .db import init_db
from .providers.base import ProviderError
from .providers.registry import get_services
from .routers import activity, approvals, auth, automations, commands, dashboard, events, planner, reminders, settings as settings_router, tasks
from .security import COOKIE_NAME, AuthError, ensure_bootstrap_user, user_for_token
from .seed import seed_database
from .services.ai import ai_status
from .services.settings import migrate_seeded_profile_name


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_bootstrap_user()
    seed_database()
    migrate_seeded_profile_name()
    get_services()
    yield


app = FastAPI(
    title="LifeDesk API",
    version=APP_VERSION,
    description="MCP-ready productivity assistant with local SQLite or MCP-backed providers.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    dashboard.router,
    commands.router,
    approvals.router,
    tasks.router,
    events.router,
    planner.router,
    activity.router,
    reminders.router,
    settings_router.router,
    automations.router,
    auth.router,
):
    app.include_router(router)


#: The only unauthenticated API surface: auth handshake and a minimal probe.
PUBLIC_API_PATHS = {
    "/api/health",
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/login",
    "/api/auth/logout",
}


@app.middleware("http")
async def require_authentication(request: Request, call_next):
    """Fail closed: every other API route needs a valid session cookie.

    The built SPA shell stays public so the login screen can render, but it
    contains no workspace data. Mutations cannot reach a provider without a
    valid HttpOnly session.
    """
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api/"):
        return await call_next(request)
    if path in PUBLIC_API_PATHS or path.startswith("/api/auth/"):
        return await call_next(request)

    user = user_for_token(request.cookies.get(COOKIE_NAME))
    if user is None:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required. Sign in to continue."},
        )
    request.state.user = user
    return await call_next(request)


@app.get("/api/health")
def health():
    services = get_services()
    return {
        "status": "ok",
        "app": APP_NAME,
        "version": APP_VERSION,
        "provider_mode": services.mode,
        "mcp_fallback": services.mode == "local-fallback",
        "ai_mode": ai_status()["mode"],
        "demo_mode": services.mode != "mcp",
    }


@app.exception_handler(ProviderError)
async def provider_error_handler(_, exc: ProviderError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(AuthError)
async def auth_error_handler(_, exc: AuthError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


# Optional single-port deployment: serve the built frontend when present.
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
FRONTEND_ROOT = FRONTEND_DIST.resolve()


def _candidate_within_dist(full_path: str) -> Path | None:
    """Resolve a request path against the build directory, refusing escapes."""
    if not FRONTEND_DIST.exists():
        return None
    try:
        candidate = (FRONTEND_DIST / full_path).resolve()
    except (OSError, ValueError):
        return None
    if candidate != FRONTEND_ROOT and FRONTEND_ROOT not in candidate.parents:
        return None
    return candidate


def resolve_frontend_file(full_path: str) -> Path | None:
    """Return a real file inside `frontend/dist`, never anything outside it.

    The SPA fallback is a path segment router, so a crafted request such as
    `/..%2F..%2Fbackend%2Flifedesk.db` would otherwise be joined onto the build
    directory and served. Resolve first, then require containment.
    """
    if full_path == "api" or full_path.startswith("api/"):
        return None
    candidate = _candidate_within_dist(full_path)
    if candidate is None or not candidate.is_file():
        return None
    return candidate


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        # Unknown API paths must 404 instead of receiving the SPA shell.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = _candidate_within_dist(full_path)
        if candidate is None:
            # Path traversal or an unusable path: never reveal anything.
            raise HTTPException(404, "Not found")
        if candidate.is_file():
            return FileResponse(candidate)
        index = FRONTEND_DIST / "index.html"
        if not index.is_file():
            raise HTTPException(404, "Not found")
        return FileResponse(index)


__all__ = ["app", "PROVIDER_MODE"]
