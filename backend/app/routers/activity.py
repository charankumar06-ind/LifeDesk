from fastapi import APIRouter, Query

from ..services.activity import activity_summary, list_activity

router = APIRouter(prefix="/api", tags=["activity"])


@router.get("/activity")
def get_activity(
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    provider: str | None = Query(default=None),
):
    if status and status not in {"success", "failed", "rejected"}:
        status = None
    entries = list_activity(limit=limit, status=status, provider_type=provider)
    return {
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "summary": activity_summary(),
    }


@router.get("/activity/summary")
def get_activity_summary():
    return activity_summary()
