from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Query

from ..domain import Event, EventCreate, EventUpdate
from ..providers.registry import get_services
from ..utils import as_date

router = APIRouter(prefix="/api", tags=["calendar"])


@router.get("/events")
def list_events(
    start: str | None = Query(default=None, description="YYYY-MM-DD, inclusive"),
    end: str | None = Query(default=None, description="YYYY-MM-DD, exclusive"),
):
    start_day = as_date(start) if start else date.today() - timedelta(days=7)
    end_day = as_date(end) if end else date.today() + timedelta(days=21)
    if end_day <= start_day:
        raise HTTPException(422, "end must be after start")
    events = get_services().calendar.list_events(
        datetime.combine(start_day, time.min), datetime.combine(end_day, time.min)
    )
    return {"events": [event.model_dump(mode="json") for event in events]}


@router.post("/events", status_code=201)
def create_event(payload: EventCreate) -> Event:
    return get_services().calendar.create_event(payload, source="local")


@router.get("/events/{event_id}")
def get_event(event_id: str) -> Event:
    event = get_services().calendar.get_event(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    return event


@router.patch("/events/{event_id}")
def update_event(event_id: str, payload: EventUpdate) -> Event:
    services = get_services()
    existing = services.calendar.get_event(event_id)
    if existing is None:
        raise HTTPException(404, "Event not found")
    merged_start = payload.start_at or existing.start_at
    merged_end = payload.end_at or existing.end_at
    if merged_end <= merged_start:
        raise HTTPException(422, "End time must be after start time")
    try:
        return services.calendar.update_event(event_id, payload)
    except KeyError:
        raise HTTPException(404, "Event not found")


@router.delete("/events/{event_id}")
def delete_event(event_id: str):
    try:
        get_services().calendar.delete_event(event_id)
    except KeyError:
        raise HTTPException(404, "Event not found")
    return {"ok": True, "deleted": event_id}
