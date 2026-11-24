"""Workflow orchestration.

Command -> deterministic interpretation -> read providers -> build a plan ->
persist *proposed* actions. Nothing is written to the calendar or task store in
this module; execution only happens through `services.execution`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from ..db import get_db
from ..domain import EventCreate, ReminderCreate, Task, TaskCreate, Workflow, WorkflowAction
from ..providers.base import ProviderError
from ..providers.registry import get_services
from ..utils import as_date, day_window, dumps, fmt_time, iso, loads, new_id, now, parse_dt
from .activity import log_activity
from .ai import get_ai_provider
from .intent import IntentResult
from .planner import DayPlan, StudyRequest, build_day_plan
from .settings import get_settings


class WorkflowError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# --------------------------------------------------------------------------- #
# Persistence helpers
# --------------------------------------------------------------------------- #

ACTION_COLUMNS = (
    "id, workflow_id, order_index, action_type, provider, title, description, payload, preview,"
    " status, result, error, idempotency_key, created_at, updated_at, executed_at"
)
WORKFLOW_COLUMNS = (
    "id, command, intent, intent_label, summary, plan, result, status, provider_mode, ai_mode,"
    " target_date, created_at, updated_at, decided_at, executed_at, error"
)


def row_to_action(row) -> WorkflowAction:
    return WorkflowAction(
        id=row["id"],
        workflow_id=row["workflow_id"],
        order_index=row["order_index"],
        action_type=row["action_type"],
        provider=row["provider"],
        title=row["title"],
        description=row["description"],
        payload=loads(row["payload"], {}),
        preview=loads(row["preview"], {}),
        status=row["status"],
        result=loads(row["result"], {}),
        error=row["error"],
        idempotency_key=row["idempotency_key"],
        created_at=parse_dt(row["created_at"]),
        updated_at=parse_dt(row["updated_at"]),
        executed_at=parse_dt(row["executed_at"]),
    )


def get_workflow(workflow_id: str) -> Workflow:
    with get_db() as conn:
        row = conn.execute(
            f"SELECT {WORKFLOW_COLUMNS} FROM workflows WHERE id = ?", (workflow_id,)
        ).fetchone()
        if row is None:
            raise WorkflowError("Workflow not found.", 404)
        actions = conn.execute(
            f"SELECT {ACTION_COLUMNS} FROM actions WHERE workflow_id = ? ORDER BY order_index, created_at",
            (workflow_id,),
        ).fetchall()
    return Workflow(
        id=row["id"],
        command=row["command"],
        intent=row["intent"],
        intent_label=row["intent_label"],
        summary=row["summary"],
        plan=loads(row["plan"], {}),
        result=loads(row["result"], {}),
        status=row["status"],
        provider_mode=row["provider_mode"],
        ai_mode=row["ai_mode"],
        target_date=row["target_date"],
        created_at=parse_dt(row["created_at"]),
        updated_at=parse_dt(row["updated_at"]),
        decided_at=parse_dt(row["decided_at"]),
        executed_at=parse_dt(row["executed_at"]),
        error=row["error"],
        actions=[row_to_action(action) for action in actions],
    )


def list_workflows(*, status: str | None = None, limit: int = 30) -> list[Workflow]:
    params: list[object] = []
    where = ""
    if status == "pending":
        where = "WHERE status IN ('pending_approval', 'executing')"
    elif status:
        where = "WHERE status = ?"
        params.append(status)
    params.append(max(1, min(limit, 100)))
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT id FROM workflows {where} ORDER BY created_at DESC LIMIT ?", params
        ).fetchall()
    return [get_workflow(row["id"]) for row in rows]


# --------------------------------------------------------------------------- #
# Proposal construction
# --------------------------------------------------------------------------- #


@dataclass
class ProposedAction:
    action_type: str
    provider: str
    title: str
    description: str
    payload: dict[str, Any]
    preview: dict[str, Any]
    idempotency_key: str = ""


@dataclass
class Proposal:
    summary: str
    steps: list[dict[str, Any]]
    actions: list[ProposedAction] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    preview: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    status: str = "pending_approval"
    error: str | None = None
    read_only: bool = False
    activity: dict[str, Any] | None = None


def _idempotency_key(action_type: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha1(f"{action_type}:{canonical}".encode("utf-8")).hexdigest()  # noqa: S324 (dedupe only)


def _action(
    *,
    action_type: str,
    provider: str,
    title: str,
    description: str,
    payload: dict[str, Any],
    preview: dict[str, Any],
) -> ProposedAction:
    return ProposedAction(
        action_type=action_type,
        provider=provider,
        title=title,
        description=description,
        payload=payload,
        preview=preview,
        idempotency_key=_idempotency_key(action_type, payload),
    )


def _step(step_id: str, title: str, detail: str, status: str = "done", provider: str | None = None) -> dict:
    return {"id": step_id, "title": title, "detail": detail, "status": status, "provider": provider}


def _base_steps(interpretation: IntentResult) -> list[dict]:
    return [
        _step(
            "interpret",
            "Interpret command",
            f"{interpretation.label} · matched rule: {interpretation.matched_rule}",
            provider="deterministic-interpreter",
        )
    ]


def _read_step(label: str, detail: str, provider: str) -> dict:
    return _step("read", label, detail, provider=provider)


def _settings_fmt(settings: dict) -> str:
    return str(settings.get("time_format", "24h"))


def plan_day_proposal(
    *,
    command: str,
    interpretation: IntentResult,
    day: date,
    settings: dict,
    study_override: StudyRequest | None = None,
) -> Proposal:
    services = get_services()
    time_format = _settings_fmt(settings)
    window_start, window_end = day_window(day, str(settings["day_start"]), str(settings["day_end"]))
    events = services.calendar.list_events(window_start, window_end)
    pending = services.tasks.list_tasks(status="open")

    entities = interpretation.entities
    study = study_override
    if study is None and entities.get("study_minutes"):
        topic = str(entities.get("study_topic") or "Focus")
        study = StudyRequest(topic=topic, minutes=int(entities["study_minutes"]))

    plan: DayPlan = build_day_plan(
        day=day,
        events=events,
        tasks=pending,
        settings=settings,
        study=study,
    )

    actions: list[ProposedAction] = []
    for block in plan.blocks:
        if block.block_type not in {"task", "study"}:
            continue
        title = block.title
        if block.block_type == "study" and not title.lower().endswith("study session"):
            title = f"{title} study session"
        payload = EventCreate(
            title=title,
            description=f"Proposed by LifeDesk: {block.reason}",
            start_at=block.start,
            end_at=block.end,
            kind=block.kind if block.kind in {"focus", "study"} else "focus",
            location="Study desk" if block.block_type == "study" else "Focus desk",
        ).model_dump(mode="json")
        actions.append(
            _action(
                action_type="create_event",
                provider="calendar",
                title=title,
                description=f"Add calendar block {fmt_time(block.start, time_format)}–{fmt_time(block.end, time_format)}.",
                payload=payload,
                preview={
                    "change": "create",
                    "entity": "calendar_event",
                    "summary": f"New event · {block.title} · {fmt_time(block.start, time_format)}–{fmt_time(block.end, time_format)}",
                    "before": None,
                    "after": {
                        "title": title,
                        "start_at": iso(block.start),
                        "end_at": iso(block.end),
                        "kind": payload["kind"],
                    },
                    "related_task_id": block.task_id,
                    "reason": block.reason,
                },
            )
        )

    conflicts = [
        {"severity": c.severity, "title": c.title, "detail": c.detail, "related_ids": c.related_ids}
        for c in plan.conflicts
    ]

    scheduled = [b for b in plan.blocks if b.block_type == "task"]
    study_block = next((b for b in plan.blocks if b.block_type == "study"), None)
    parts = [f"{len(scheduled)} focus block(s) proposed from {len(pending)} pending task(s)"]
    if study_block:
        parts.append(
            f"{study_block.title} protected at {fmt_time(study_block.start, time_format)}–"
            f"{fmt_time(study_block.end, time_format)}"
        )
    if conflicts:
        parts.append(f"{len(conflicts)} conflict(s) flagged")
    summary = "; ".join(parts) + ". Nothing has been written yet."

    steps = _base_steps(interpretation) + [
        _read_step(
            "Read pending tasks",
            f"{len(pending)} open task(s) from {services.tasks.info.label} ({services.tasks.info.transport}).",
            services.tasks.info.key,
        ),
        _read_step(
            "Read calendar",
            f"{len(events)} event(s) between {fmt_time(window_start, time_format)} and {fmt_time(window_end, time_format)}.",
            services.calendar.info.key,
        ),
        _step(
            "rank",
            "Rank and allocate",
            "Deadline proximity first, then priority; explicit study request protected; "
            f"{settings['buffer_minutes']}-minute buffers between blocks.",
        ),
        _step("conflicts", "Conflict check", f"{len(conflicts)} finding(s) reported in the plan."),
        _step(
            "propose",
            "Propose changes",
            f"{len(actions)} calendar action(s) awaiting approval. No data written.",
            status="awaiting_approval" if actions else "skipped",
        ),
    ]

    proposal = Proposal(
        summary=summary,
        steps=steps,
        actions=actions,
        rationale=plan.rationale,
        conflicts=conflicts,
        preview={"plan": plan.as_dict(time_format), "command": command},
        status="pending_approval" if actions else "failed",
        error=None if actions else "No schedulable blocks were found for this day.",
    )
    return proposal


def _overlap_conflicts(events, start: datetime, end: datetime, time_format: str) -> list[dict]:
    conflicts = []
    for event in events:
        if event.start_at < end and event.end_at > start:
            conflicts.append(
                {
                    "severity": "warning",
                    "title": "Time already booked",
                    "detail": (
                        f"'{event.title}' occupies {fmt_time(event.start_at, time_format)}–"
                        f"{fmt_time(event.end_at, time_format)}."
                    ),
                    "related_ids": [event.id],
                }
            )
    return conflicts


def study_proposal(*, interpretation: IntentResult, day: date, settings: dict) -> Proposal:
    services = get_services()
    time_format = _settings_fmt(settings)
    window_start, window_end = day_window(day, str(settings["day_start"]), str(settings["day_end"]))
    events = services.calendar.list_events(window_start, window_end)
    minutes = int(interpretation.entities.get("minutes") or settings["default_study_minutes"])
    topic = str(interpretation.entities.get("topic") or "Focus")
    study = StudyRequest(topic=topic, minutes=minutes)
    plan = build_day_plan(day=day, events=events, tasks=[], settings=settings, study=study)
    study_block = next((block for block in plan.blocks if block.block_type == "study"), None)
    conflicts = [
        {"severity": c.severity, "title": c.title, "detail": c.detail, "related_ids": c.related_ids}
        for c in plan.conflicts
    ]
    steps = _base_steps(interpretation) + [
        _read_step(
            "Read calendar",
            f"{len(events)} event(s) on {day.isoformat()} from {services.calendar.info.label}.",
            services.calendar.info.key,
        ),
        _step("gap", "Find free gap", f"Looking for one contiguous {minutes}-minute slot inside the working window."),
    ]

    if study_block is None:
        steps.append(_step("propose", "Propose changes", "No slot fits, so nothing is proposed.", status="failed"))
        return Proposal(
            summary=f"No {minutes}-minute gap remains on {day.isoformat()}.",
            steps=steps,
            conflicts=conflicts,
            preview={"plan": plan.as_dict(time_format)},
            status="failed",
            error=(
                f"There is no free {minutes}-minute window between "
                f"{fmt_time(window_start, time_format)} and {fmt_time(window_end, time_format)}. "
                "Try a shorter session or a different day."
            ),
        )

    title = f"{topic} study session" if topic != "Focus" else "Study session"
    payload = EventCreate(
        title=title,
        description=f"Protected {minutes}-minute focus block requested via the command center.",
        start_at=study_block.start,
        end_at=study_block.end,
        kind="study",
        location="Study desk",
    ).model_dump(mode="json")
    action = _action(
        action_type="create_event",
        provider="calendar",
        title=title,
        description=f"Reserve {fmt_time(study_block.start, time_format)}–{fmt_time(study_block.end, time_format)}.",
        payload=payload,
        preview={
            "change": "create",
            "entity": "calendar_event",
            "summary": f"New study block · {fmt_time(study_block.start, time_format)}–{fmt_time(study_block.end, time_format)}",
            "before": None,
            "after": payload,
            "reason": study_block.reason,
        },
    )
    steps.append(_step("propose", "Propose changes", "1 calendar action awaiting approval. No data written.", status="awaiting_approval"))
    return Proposal(
        summary=(
            f"One {minutes}-minute {title.lower()} proposed at "
            f"{fmt_time(study_block.start, time_format)}–{fmt_time(study_block.end, time_format)}."
        ),
        steps=steps,
        actions=[action],
        rationale=plan.rationale,
        conflicts=conflicts,
        preview={"plan": plan.as_dict(time_format)},
    )


def reminder_proposal(*, interpretation: IntentResult, settings: dict) -> Proposal:
    entities = interpretation.entities
    title = str(entities.get("title") or "Reminder")
    remind_at = parse_dt(str(entities.get("remind_at"))) or (now() + timedelta(hours=1))
    payload = ReminderCreate(title=title, note="", remind_at=remind_at).model_dump(mode="json")
    time_format = _settings_fmt(settings)
    action = _action(
        action_type="create_reminder",
        provider="reminder",
        title=f"Reminder: {title}",
        description=f"Notify {remind_at.strftime('%d %b')} at {fmt_time(remind_at, time_format)}.",
        payload=payload,
        preview={
            "change": "create",
            "entity": "reminder",
            "summary": f"New reminder · {title} · {remind_at.strftime('%d %b %H:%M')}",
            "before": None,
            "after": payload,
        },
    )
    steps = _base_steps(interpretation) + [
        _step("resolve_time", "Resolve time", f"Scheduled for {remind_at.strftime('%d %b %Y')} at {fmt_time(remind_at, time_format)}."),
        _step("propose", "Propose changes", "1 reminder action awaiting approval.", status="awaiting_approval"),
    ]
    return Proposal(
        summary=f"Reminder '{title}' proposed for {remind_at.strftime('%d %b at %H:%M')}.",
        steps=steps,
        actions=[action],
        preview={"reminder": payload},
    )


def event_proposal(*, interpretation: IntentResult, day: date, settings: dict) -> Proposal:
    services = get_services()
    time_format = _settings_fmt(settings)
    entities = interpretation.entities
    title = str(entities.get("title") or "Meeting")
    start_time = str(entities.get("start_time") or "10:00")
    hour, minute = (int(part) for part in start_time.split(":"))
    start = datetime.combine(day, time(hour, minute))
    end = start + timedelta(minutes=int(entities.get("minutes") or 60))
    existing = services.calendar.list_events(start, end)
    conflicts = _overlap_conflicts(existing, start, end, time_format)
    payload = EventCreate(
        title=title,
        description="Scheduled via the LifeDesk command center.",
        start_at=start,
        end_at=end,
        kind="meeting",
    ).model_dump(mode="json")
    action = _action(
        action_type="create_event",
        provider="calendar",
        title=title,
        description=f"Reserve {fmt_time(start, time_format)}–{fmt_time(end, time_format)} on {day.isoformat()}.",
        payload=payload,
        preview={
            "change": "create",
            "entity": "calendar_event",
            "summary": f"New event · {title} · {fmt_time(start, time_format)}–{fmt_time(end, time_format)}",
            "before": None,
            "after": payload,
            "conflicts": conflicts,
        },
    )
    steps = _base_steps(interpretation) + [
        _read_step(
            "Read calendar",
            f"{len(existing)} event(s) already in the slot.",
            services.calendar.info.key,
        ),
        _step("propose", "Propose changes", "1 calendar action awaiting approval. No data written.", status="awaiting_approval"),
    ]
    return Proposal(
        summary=f"'{title}' proposed for {day.strftime('%d %b')} at {fmt_time(start, time_format)}.",
        steps=steps,
        actions=[action],
        conflicts=conflicts,
        preview={"event": payload},
    )


def task_proposal(*, interpretation: IntentResult, settings: dict) -> Proposal:
    entities = interpretation.entities
    title = str(entities.get("title") or "New task")
    due_date = entities.get("due_date")
    due_at = datetime.combine(as_date(str(due_date)), time(18, 0)) if due_date else None
    payload = TaskCreate(
        title=title,
        priority=entities.get("priority") or "medium",
        due_at=due_at,
        estimate_minutes=60,
    ).model_dump(mode="json")
    action = _action(
        action_type="create_task",
        provider="task",
        title=f"Task: {title}",
        description="Add to the task list." + (f" Due {due_at.strftime('%d %b %H:%M')}." if due_at else ""),
        payload=payload,
        preview={
            "change": "create",
            "entity": "task",
            "summary": f"New task · {title}",
            "before": None,
            "after": payload,
        },
    )
    steps = _base_steps(interpretation) + [
        _step("propose", "Propose changes", "1 task action awaiting approval.", status="awaiting_approval")
    ]
    return Proposal(summary=f"Task '{title}' proposed.", steps=steps, actions=[action], preview={"task": payload})


def pending_tasks_proposal(*, interpretation: IntentResult) -> Proposal:
    services = get_services()
    tasks = services.tasks.list_tasks(status="open")
    tasks_payload = [task.model_dump(mode="json") for task in tasks]
    steps = _base_steps(interpretation) + [
        _read_step(
            "Read pending tasks",
            f"{len(tasks)} open task(s) from {services.tasks.info.label} ({services.tasks.info.transport}).",
            services.tasks.info.key,
        ),
        _step("report", "Report", "Read-only request: no actions proposed, no data modified.", status="completed"),
    ]
    return Proposal(
        summary=f"{len(tasks)} pending task(s). Read-only — nothing was modified.",
        steps=steps,
        actions=[],
        result={"tasks": tasks_payload, "count": len(tasks)},
        status="completed",
        read_only=True,
        activity={
            "provider_type": "task",
            "provider_name": services.tasks.info.key,
            "operation": "list_tasks",
            "status": "success",
            "message": f"Returned {len(tasks)} pending task(s).",
            "detail": {"count": len(tasks), "status_filter": "open"},
        },
    )


def unsupported_proposal(*, interpretation: IntentResult) -> Proposal:
    steps = [
        _step("interpret", "Interpret command", interpretation.explanation, status="failed", provider="deterministic-interpreter"),
        _step("propose", "Propose changes", "No actions were proposed.", status="skipped"),
    ]
    return Proposal(
        summary="Command not understood — nothing was executed.",
        steps=steps,
        status="failed",
        error=interpretation.explanation,
        activity={
            "provider_type": "ai",
            "provider_name": "deterministic-interpreter",
            "operation": "interpret_command",
            "status": "failed",
            "message": "Unsupported command. Supported intents: plan my day, pending tasks, study session, reminder, meeting, task.",
            "detail": {"command": interpretation.explanation},
        },
    )


# --------------------------------------------------------------------------- #
# Command entry point
# --------------------------------------------------------------------------- #


def run_command(command: str) -> Workflow:
    command = (command or "").strip()
    if not command:
        raise WorkflowError("Enter a command before running the workflow.", 422)
    if len(command) > 600:
        raise WorkflowError("Commands are limited to 600 characters.", 422)

    settings = get_settings()
    ai_provider = get_ai_provider()
    interpretation = ai_provider.interpret(command)
    day = as_date(str(interpretation.entities.get("date") or "")) if interpretation.entities.get("date") or interpretation.intent == "plan_day" else date.today()

    if not interpretation.supported:
        proposal = unsupported_proposal(interpretation=interpretation)
    elif interpretation.intent == "plan_day":
        proposal = plan_day_proposal(command=command, interpretation=interpretation, day=day, settings=settings)
    elif interpretation.intent == "list_pending":
        proposal = pending_tasks_proposal(interpretation=interpretation)
    elif interpretation.intent == "schedule_study":
        proposal = study_proposal(interpretation=interpretation, day=day, settings=settings)
    elif interpretation.intent == "create_reminder":
        proposal = reminder_proposal(interpretation=interpretation, settings=settings)
    elif interpretation.intent == "schedule_event":
        proposal = event_proposal(interpretation=interpretation, day=day, settings=settings)
    elif interpretation.intent == "create_task":
        proposal = task_proposal(interpretation=interpretation, settings=settings)
    else:  # pragma: no cover - defensive
        proposal = unsupported_proposal(interpretation=interpretation)

    workflow = _persist_workflow(
        command=command,
        interpretation=interpretation,
        proposal=proposal,
        settings=settings,
        day=day,
        ai_mode=ai_provider.info.mode,
    )

    if proposal.activity:
        activity = proposal.activity
        log_activity(
            provider_type=str(activity["provider_type"]),
            provider_name=str(activity["provider_name"]),
            operation=str(activity["operation"]),
            status=str(activity["status"]),
            message=str(activity["message"]),
            workflow_id=workflow.id,
            detail=activity.get("detail") or {},
            simulated=True,
        )
    if proposal.status == "failed" and not proposal.activity:
        log_activity(
            provider_type="workflow",
            provider_name="local-workflow-engine",
            operation="propose_actions",
            status="failed",
            message=proposal.error or "Workflow could not propose actions.",
            workflow_id=workflow.id,
            detail={"intent": interpretation.intent},
        )
    return workflow


def create_plan_proposal(day: date) -> Workflow:
    """Used by the Daily Planner page to send its schedule to approvals."""
    settings = get_settings()
    interpretation = IntentResult(
        intent="plan_day",
        label="Plan my day",
        supported=True,
        confidence=1.0,
        entities={"date": day.isoformat()},
        explanation="Requested from the Daily Planner using the local task and calendar providers.",
        matched_rule="planner/propose",
    )
    proposal = plan_day_proposal(
        command=f"Plan my day for {day.isoformat()}",
        interpretation=interpretation,
        day=day,
        settings=settings,
    )
    workflow = _persist_workflow(
        command=f"Plan my day for {day.isoformat()}",
        interpretation=interpretation,
        proposal=proposal,
        settings=settings,
        day=day,
        ai_mode=get_ai_provider().info.mode,
    )
    if proposal.status == "failed":
        log_activity(
            provider_type="workflow",
            provider_name="local-workflow-engine",
            operation="propose_actions",
            status="failed",
            message=proposal.error or "No actions proposed.",
            workflow_id=workflow.id,
            detail={"intent": "plan_day", "source": "planner"},
        )
    return workflow


def _persist_workflow(
    *,
    command: str,
    interpretation: IntentResult,
    proposal: Proposal,
    settings: dict,
    day: date,
    ai_mode: str,
) -> Workflow:
    workflow_id = new_id("wf")
    stamp = iso(now())

    actions = proposal.actions
    keys = [action.idempotency_key for action in actions]
    duplicates: list[dict[str, str]] = []
    existing: dict[str, str] = {}
    dead_rows: list = []
    if keys:
        placeholders = ",".join("?" for _ in keys)
        with get_db() as conn:
            # Only live proposals block identical actions. Rows from rejected or
            # failed workflows are set aside below so the user can ask for the
            # same plan again and retry; their dedupe key is handed back rather
            # than deleted, keeping the historical workflow intact.
            rows = conn.execute(
                "SELECT a.id, a.idempotency_key, a.workflow_id, w.status FROM actions a"
                " JOIN workflows w ON w.id = a.workflow_id"
                f" WHERE a.idempotency_key IN ({placeholders})",
                keys,
            ).fetchall()
        for row in rows:
            if row["status"] in {"rejected", "failed"}:
                dead_rows.append(row)
            else:
                existing[row["idempotency_key"]] = row["workflow_id"]
    kept: list[ProposedAction] = []
    for action in actions:
        if action.idempotency_key in existing:
            duplicates.append(
                {
                    "title": action.title,
                    "reason": f"Identical action already proposed in workflow {existing[action.idempotency_key]}.",
                }
            )
        else:
            kept.append(action)

    status = proposal.status
    error = proposal.error
    if duplicates and not kept and proposal.actions:
        status = "failed"
        error = (
            "Nothing new to propose: an identical action is already pending or executed "
            f"(workflow {existing[actions[0].idempotency_key]}). Duplicate actions are blocked."
        )

    plan = {
        "steps": proposal.steps,
        "rationale": proposal.rationale,
        "conflicts": proposal.conflicts,
        "preview": proposal.preview,
        "skipped_duplicates": duplicates,
        "ai": {
            "mode": ai_mode,
            "label": "Deterministic intent interpreter",
            "llm_used": False,
            "explanation": interpretation.explanation,
            "matched_rule": interpretation.matched_rule,
            "confidence": interpretation.confidence,
        },
        "providers": get_services().provider_infos(),
    }

    kept_keys = {action.idempotency_key for action in kept}

    with get_db() as conn:
        # Free the keys held by rejected/failed actions that this proposal reuses.
        # The historical row keeps a unique, still-traceable token.
        for row in dead_rows:
            if row["idempotency_key"] in kept_keys:
                conn.execute(
                    "UPDATE actions SET idempotency_key = ? WHERE id = ?",
                    (f"{row['idempotency_key']}:retry:{row['workflow_id']}", row["id"]),
                )
        conn.execute(
            "INSERT INTO workflows (id, command, intent, intent_label, summary, plan, result, status,"
            " provider_mode, ai_mode, target_date, created_at, updated_at, decided_at, executed_at, error)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)",
            (
                workflow_id,
                command,
                interpretation.intent,
                interpretation.label,
                proposal.summary,
                dumps(plan),
                dumps(proposal.result),
                status,
                get_services().mode,
                ai_mode,
                day.isoformat(),
                stamp,
                stamp,
                error,
            ),
        )
        for index, action in enumerate(kept):
            conn.execute(
                "INSERT INTO actions (id, workflow_id, order_index, action_type, provider, title, description,"
                " payload, preview, status, result, error, idempotency_key, created_at, updated_at, executed_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', '{}', '', ?, ?, ?, NULL)",
                (
                    new_id("act"),
                    workflow_id,
                    index,
                    action.action_type,
                    action.provider,
                    action.title,
                    action.description,
                    dumps(action.payload),
                    dumps(action.preview),
                    action.idempotency_key,
                    stamp,
                    stamp,
                ),
            )
    return get_workflow(workflow_id)
