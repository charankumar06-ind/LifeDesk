from datetime import date, datetime, time, timedelta

from fastapi import APIRouter

from ..providers.registry import get_services
from ..services.activity import list_activity
from ..services.settings import get_settings
from ..services.workflows import list_workflows
from ..utils import minutes_between

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard():
    services = get_services()
    settings = get_settings()
    today = date.today()
    day_start = datetime.combine(today, time.min)
    day_end = day_start + timedelta(days=1)

    events = services.calendar.list_events(day_start, day_end)
    upcoming_events = services.calendar.list_events(day_end, day_end + timedelta(days=7))[:4]
    all_tasks = services.tasks.list_tasks()
    pending = [task for task in all_tasks if task.status != "done"]
    completed_today = [task for task in all_tasks if task.completed_at and task.completed_at.date() == today]
    reminders = services.reminders.list_reminders(status="pending")
    recent_activity = list_activity(limit=8)
    pending_workflows = list_workflows(status="pending", limit=20)
    now_ts = datetime.now()

    next_event = next((event for event in events if event.end_at >= now_ts), None)
    overdue = [task for task in pending if task.due_at and task.due_at < now_ts]
    focus_minutes = sum(
        minutes_between(event.start_at, event.end_at) for event in events if event.kind in {"focus", "study"}
    )
    scheduled_minutes = sum(minutes_between(event.start_at, event.end_at) for event in events)
    done_total = sum(1 for task in all_tasks if task.status == "done")
    completion_rate = round(done_total / len(all_tasks) * 100) if all_tasks else 0

    weekly = []
    for offset in range(6, -1, -1):
        day_value = today - timedelta(days=offset)
        weekly.append(
            {
                "date": day_value.isoformat(),
                "label": day_value.strftime("%a"),
                "count": sum(1 for task in all_tasks if task.completed_at and task.completed_at.date() == day_value),
            }
        )

    return {
        "date": today.isoformat(),
        "settings": {
            "display_name": settings["display_name"],
            "time_format": settings["time_format"],
            "day_start": settings["day_start"],
            "day_end": settings["day_end"],
        },
        "events_today": [event.model_dump(mode="json") for event in events],
        "next_event": next_event.model_dump(mode="json") if next_event else None,
        "upcoming_events": [event.model_dump(mode="json") for event in upcoming_events],
        "pending_tasks": [task.model_dump(mode="json") for task in pending],
        "completed_today": [task.model_dump(mode="json") for task in completed_today],
        "reminders": [reminder.model_dump(mode="json") for reminder in reminders],
        "recent_activity": [entry.model_dump(mode="json") for entry in recent_activity],
        "stats": {
            "pending_count": len(pending),
            "completed_today": len(completed_today),
            "completion_rate": completion_rate,
            "overdue_count": len(overdue),
            "urgent_count": sum(1 for task in pending if task.priority in {"urgent", "high"}),
            "focus_minutes_today": focus_minutes,
            "scheduled_minutes_today": scheduled_minutes,
            "free_minutes_today": max(0, 10 * 60 - scheduled_minutes),
            "weekly_completions": weekly,
        },
        "pending_approvals": len(pending_workflows),
    }
