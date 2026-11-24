from fastapi import APIRouter, HTTPException, Query

from ..providers.registry import get_services

router = APIRouter(prefix="/api", tags=["reminders"])


@router.get("/reminders")
def list_reminders(status: str | None = Query(default=None)):
    if status not in {None, "pending", "dismissed"}:
        raise HTTPException(422, "status must be pending or dismissed")
    reminders = get_services().reminders.list_reminders(status=status)
    return {"reminders": [reminder.model_dump(mode="json") for reminder in reminders]}


@router.post("/reminders/{reminder_id}/dismiss")
def dismiss_reminder(reminder_id: str):
    try:
        return get_services().reminders.dismiss_reminder(reminder_id)
    except KeyError:
        raise HTTPException(404, "Reminder not found")
