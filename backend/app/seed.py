"""Idempotent demo seeding.

Seeded content is relative to the current date so the prototype always shows a
live-looking day, and it is only inserted once.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .config import SEED_DEMO_DATA
from .db import get_db
from .providers.local_calendar import seed_event
from .providers.local_task import seed_task
from .services.settings import DEFAULT_SETTINGS
from .utils import dumps, iso, new_id, now

SEED_KEY = "seeded_v1"


def _at(base: date, offset_days: int, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(base + timedelta(days=offset_days), time(hour, minute))


def _activity(
    conn,
    *,
    base: date,
    days_ago: int,
    hour: int,
    minute: int,
    provider_type: str,
    provider_name: str,
    operation: str,
    status: str,
    message: str,
    workflow_id: str | None = None,
    action_id: str | None = None,
    detail: dict | None = None,
) -> None:
    conn.execute(
        "INSERT INTO activity (id, workflow_id, action_id, provider_type, provider_name, operation,"
        " status, message, simulated, detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
        (
            new_id("act"),
            workflow_id,
            action_id,
            provider_type,
            provider_name,
            operation,
            status,
            message,
            dumps(detail or {"seeded": True}),
            iso(_at(base, -days_ago, hour, minute)),
        ),
    )


def _seed_content(conn) -> None:
    today = date.today()

    # ----- calendar --------------------------------------------------------
    seed_event(conn, title="Team standup", start=_at(today, 0, 9, 30), end=_at(today, 0, 10, 0),
               location="Room 2B", description="Daily sync with the project team.")
    seed_event(conn, title="Research methods lecture", start=_at(today, 0, 11, 0), end=_at(today, 0, 12, 30),
               location="Lecture Hall C")
    seed_event(conn, title="Design review — LifeDesk prototype", start=_at(today, 0, 14, 0),
               end=_at(today, 0, 15, 0), location="Meet")
    seed_event(conn, title="Advisor check-in", start=_at(today, 0, 16, 30), end=_at(today, 0, 17, 0),
               location="Office 214")
    seed_event(conn, title="Algorithms lab", start=_at(today, 1, 10, 0), end=_at(today, 1, 11, 30),
               location="Lab 3")
    seed_event(conn, title="Study group — statistics", start=_at(today, 1, 15, 0), end=_at(today, 1, 16, 0),
               location="Library, floor 2")
    seed_event(conn, title="Dentist appointment", start=_at(today, 3, 9, 0), end=_at(today, 3, 9, 45),
               kind="personal", location="Northside Clinic")

    # ----- tasks -----------------------------------------------------------
    seed_task(
        conn,
        title="Data structures assignment — graph traversal proofs",
        priority="urgent",
        due_at=_at(today, 0, 23, 0),
        estimate_minutes=90,
        tags=["Coursework", "Algorithms"],
        description="Two proofs and one implementation. Submit through the course portal.",
    )
    seed_task(
        conn,
        title="Research methods essay draft",
        priority="high",
        due_at=_at(today, 1, 17, 0),
        estimate_minutes=90,
        tags=["Coursework", "Writing"],
        description="First full draft with citations; peer review opens tomorrow evening.",
    )
    seed_task(
        conn,
        title="Prepare sprint demo notes",
        priority="high",
        due_at=_at(today, 2, 12, 0),
        estimate_minutes=45,
        tags=["Work"],
    )
    seed_task(
        conn,
        title="Weekly budget review",
        priority="medium",
        status="in_progress",
        due_at=_at(today, 2, 18, 0),
        estimate_minutes=30,
        tags=["Personal"],
    )
    seed_task(
        conn,
        title="Read 'The Design of Everyday Things' ch. 4",
        priority="low",
        due_at=_at(today, 4, 20, 0),
        estimate_minutes=45,
        tags=["Reading"],
    )
    seed_task(
        conn,
        title="Morning inbox triage",
        priority="low",
        status="done",
        completed_at=_at(today, 0, 8, 55),
        estimate_minutes=20,
        tags=["Admin"],
    )
    seed_task(
        conn,
        title="Team standup notes",
        priority="medium",
        status="done",
        completed_at=_at(today, 0, 10, 15),
        estimate_minutes=15,
        tags=["Work"],
    )
    seed_task(conn, title="Algorithms problem set 3", priority="high", status="done",
              completed_at=_at(today, -1, 18, 40), estimate_minutes=90, tags=["Coursework"])
    seed_task(conn, title="Course reading: interaction design", priority="low", status="done",
              completed_at=_at(today, -2, 20, 10), estimate_minutes=45, tags=["Reading"])
    seed_task(conn, title="Renew library loans", priority="low", status="done",
              completed_at=_at(today, -3, 12, 5), estimate_minutes=15, tags=["Admin"])
    seed_task(conn, title="Plan weekly review", priority="low", status="done",
              completed_at=_at(today, -5, 19, 30), estimate_minutes=30, tags=["Personal"])
    seed_task(conn, title="Submit lab safety form", priority="medium", status="done",
              completed_at=_at(today, -6, 16, 20), estimate_minutes=20, tags=["Coursework"])

    # ----- reminders -------------------------------------------------------
    for title, note, remind_at in (
        ("Submit course feedback", "End-of-term evaluation closes Friday.", _at(today, 1, 9, 0)),
        ("Call bank about card", "Ask about the replacement card delivery.", _at(today, 2, 17, 30)),
    ):
        conn.execute(
            "INSERT INTO reminders (id, title, note, remind_at, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'pending', ?, ?)",
            (new_id("rem"), title, note, iso(remind_at), iso(now()), iso(now())),
        )

    # ----- one completed + one rejected workflow ---------------------------
    study_event_id = seed_event(
        conn,
        title="Deep work: statistics problem set",
        start=_at(today, -1, 15, 0),
        end=_at(today, -1, 16, 30),
        kind="focus",
        location="Study desk",
        description="Created by LifeDesk after approval.",
        source="workflow",
    )

    completed_wf = new_id("wf")
    completed_action = new_id("act")
    completed_plan = {
        "steps": [
            {"id": "interpret", "title": "Interpret command", "detail": "Schedule a study session · deterministic rule", "status": "done", "provider": "deterministic-interpreter"},
            {"id": "read", "title": "Read calendar", "detail": "3 event(s) on the target day from Local Calendar.", "status": "done", "provider": "local-calendar"},
            {"id": "propose", "title": "Propose changes", "detail": "1 calendar action awaiting approval.", "status": "done", "provider": None},
        ],
        "rationale": ["Requested session was protected in the first conflict-free 90-minute slot."],
        "conflicts": [],
        "preview": {},
        "skipped_duplicates": [],
        "ai": {"mode": "deterministic", "label": "Deterministic intent interpreter", "llm_used": False,
               "explanation": "Matched the study-session rule.", "matched_rule": "schedule_study / 'study session'", "confidence": 0.92},
        "providers": [],
    }
    payload = {
        "title": "Deep work: statistics problem set",
        "description": "Created by LifeDesk after approval.",
        "start_at": iso(_at(today, -1, 15, 0)),
        "end_at": iso(_at(today, -1, 16, 30)),
        "location": "Study desk",
        "kind": "focus",
    }
    conn.execute(
        "INSERT INTO workflows (id, command, intent, intent_label, summary, plan, result, status, provider_mode,"
        " ai_mode, target_date, created_at, updated_at, decided_at, executed_at, error)"
        " VALUES (?, ?, 'schedule_study', 'Schedule a study session', ?, ?, ?, 'completed', 'local',"
        " 'deterministic', ?, ?, ?, ?, ?, NULL)",
        (
            completed_wf,
            "Schedule a 90-minute statistics study session",
            "One 90-minute statistics session was added after approval.",
            dumps(completed_plan),
            dumps({"executed": 1, "failed": 0, "failures": [], "status": "completed"}),
            (today - timedelta(days=1)).isoformat(),
            iso(_at(today, -1, 9, 0)),
            iso(_at(today, -1, 9, 5)),
            iso(_at(today, -1, 9, 6)),
            iso(_at(today, -1, 9, 6)),
        ),
    )
    conn.execute(
        "INSERT INTO actions (id, workflow_id, order_index, action_type, provider, title, description, payload,"
        " preview, status, result, error, idempotency_key, created_at, updated_at, executed_at)"
        " VALUES (?, ?, 0, 'create_event', 'calendar', 'Statistics study session',"
        " 'Reserve 15:00–16:30.', ?, ?, 'executed', ?, '', 'seed-completed-action', ?, ?, ?)",
        (
            completed_action,
            completed_wf,
            dumps(payload),
            dumps({"change": "create", "entity": "calendar_event",
                   "summary": "New study block · 15:00–16:30", "before": None, "after": payload}),
            dumps({"event_id": study_event_id}),
            iso(_at(today, -1, 9, 0)),
            iso(_at(today, -1, 9, 6)),
            iso(_at(today, -1, 9, 6)),
        ),
    )

    rejected_wf = new_id("wf")
    rejected_action = new_id("act")
    rejected_plan = {
        "steps": [
            {"id": "interpret", "title": "Interpret command", "detail": "Plan my day · deterministic rule", "status": "done", "provider": "deterministic-interpreter"},
            {"id": "approval", "title": "Propose changes", "detail": "2 calendar actions awaited approval.", "status": "done", "provider": None},
        ],
        "rationale": ["Urgent priorities were placed first."],
        "conflicts": [],
        "preview": {},
        "skipped_duplicates": [],
        "ai": {"mode": "deterministic", "label": "Deterministic intent interpreter", "llm_used": False,
               "explanation": "Matched the day-planning rule.", "matched_rule": "plan_day / 'plan my day'", "confidence": 0.96},
        "providers": [],
    }
    conn.execute(
        "INSERT INTO workflows (id, command, intent, intent_label, summary, plan, result, status, provider_mode,"
        " ai_mode, target_date, created_at, updated_at, decided_at, executed_at, error)"
        " VALUES (?, 'Plan my day', 'plan_day', 'Plan my day', ?, ?, '{}', 'rejected', 'local',"
        " 'deterministic', ?, ?, ?, ?, NULL, 'All proposed actions were rejected.')",
        (
            rejected_wf,
            "2 focus blocks were proposed; both were rejected.",
            dumps(rejected_plan),
            (today - timedelta(days=2)).isoformat(),
            iso(_at(today, -2, 8, 40)),
            iso(_at(today, -2, 8, 47)),
            iso(_at(today, -2, 8, 47)),
        ),
    )
    conn.execute(
        "INSERT INTO actions (id, workflow_id, order_index, action_type, provider, title, description, payload,"
        " preview, status, result, error, idempotency_key, created_at, updated_at, executed_at)"
        " VALUES (?, ?, 0, 'create_event', 'calendar', 'Focus: Weekly budget review',"
        " 'Add calendar block 10:00–10:30.', '{}', '{}', 'rejected', '{}', '', 'seed-rejected-action', ?, ?, NULL)",
        (rejected_action, rejected_wf, iso(_at(today, -2, 8, 40)), iso(_at(today, -2, 8, 47))),
    )

    # ----- activity history ------------------------------------------------
    _activity(conn, base=today, days_ago=0, hour=10, minute=16, provider_type="task",
              provider_name="local-tasks", operation="update_task", status="success",
              message="Marked task 'Team standup notes' as done.",
              detail={"task_id": "seed", "result": "done", "seeded": True})
    _activity(conn, base=today, days_ago=1, hour=9, minute=6, provider_type="calendar",
              provider_name="local-calendar", operation="create_event", status="success",
              message="Created calendar event 'Deep work: statistics problem set' (15:00–16:30).",
              workflow_id=completed_wf, action_id=completed_action,
              detail={"event_id": study_event_id, "seeded": True})
    _activity(conn, base=today, days_ago=1, hour=9, minute=6, provider_type="workflow",
              provider_name="local-workflow-engine", operation="execute_workflow", status="success",
              message="Workflow finished: 1 action(s) executed.", workflow_id=completed_wf,
              detail={"executed": 1, "failed": 0, "seeded": True})
    _activity(conn, base=today, days_ago=2, hour=8, minute=47, provider_type="calendar",
              provider_name="local-calendar", operation="create_event", status="rejected",
              message="Rejected by user: Focus: Weekly budget review",
              workflow_id=rejected_wf, action_id=rejected_action, detail={"decision": "reject", "seeded": True})
    _activity(conn, base=today, days_ago=2, hour=8, minute=20, provider_type="calendar",
              provider_name="local-calendar", operation="create_event", status="failed",
              message="Calendar write failed: slot overlaps 'Advisor check-in'.",
              detail={"error": "overlap", "seeded": True})
    _activity(conn, base=today, days_ago=3, hour=12, minute=5, provider_type="task",
              provider_name="local-tasks", operation="list_tasks", status="success",
              message="Returned 4 pending task(s).", detail={"count": 4, "seeded": True})


def seed_database() -> bool:
    with get_db() as conn:
        already = conn.execute("SELECT value FROM meta WHERE key = ?", (SEED_KEY,)).fetchone()
        if already:
            return False
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, str(value))
            )
        if SEED_DEMO_DATA:
            _seed_content(conn)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (SEED_KEY, iso(now()))
        )
    return True
