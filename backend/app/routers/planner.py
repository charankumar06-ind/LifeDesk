from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..providers.registry import get_services
from ..services.intent import IntentResult
from ..services.planner import build_day_plan
from ..services.settings import get_settings
from ..services.workflows import WorkflowError, create_plan_proposal
from ..utils import as_date, day_window

router = APIRouter(prefix="/api", tags=["planner"])


class ProposeRequest(BaseModel):
    date: str | None = None


@router.get("/planner/day")
def planner_day(date_value: str | None = Query(default=None, alias="date")):
    settings = get_settings()
    services = get_services()
    day: date = as_date(date_value)
    window_start, window_end = day_window(day, str(settings["day_start"]), str(settings["day_end"]))
    events = services.calendar.list_events(window_start, window_end)
    pending = services.tasks.list_tasks(status="open")
    plan = build_day_plan(day=day, events=events, tasks=pending, settings=settings)
    return {
        "plan": plan.as_dict(str(settings["time_format"])),
        "pending_tasks": [task.model_dump(mode="json") for task in pending],
        "window": {
            "start": str(settings["day_start"]),
            "end": str(settings["day_end"]),
            "buffer_minutes": settings["buffer_minutes"],
        },
    }


@router.post("/planner/propose", status_code=201)
def propose_day_plan(payload: ProposeRequest):
    try:
        return create_plan_proposal(as_date(payload.date))
    except WorkflowError as exc:
        raise HTTPException(exc.status_code, str(exc))
