from fastapi import APIRouter

from ..services.automations import automation_catalog

router = APIRouter(prefix="/api", tags=["automations"])


@router.get("/automations")
def get_automations():
    """Return the automation catalog with live readiness for the active provider."""
    return automation_catalog()
