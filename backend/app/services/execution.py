"""Approval decisions + guarded execution.

Guarantees:
* only actions a human approved are executed;
* a workflow cannot be executed twice (status guard + atomic per-action claim);
* every executed, rejected or failed tool call appears in the Activity Monitor.
"""

from __future__ import annotations

from typing import Any, Literal

from ..db import get_db
from ..domain import EmailMessage, EventCreate, ReminderCreate, TaskCreate, TaskUpdate, Workflow
from ..providers.base import ProviderInfo
from ..providers.registry import get_services
from ..utils import dumps, fmt_time, iso, new_id, now
from .activity import log_activity
from .settings import get_settings
from .workflows import ACTION_COLUMNS, WorkflowError, get_workflow, row_to_action

Decision = Literal["approve", "reject"]

_PROVIDER_INFO = {
    "calendar": lambda: get_services().calendar.info,
    "task": lambda: get_services().tasks.info,
    "reminder": lambda: get_services().reminders.info,
    "mail": lambda: get_services().mail.info,
}


def _provider_info(provider: str) -> ProviderInfo:
    getter = _PROVIDER_INFO.get(provider)
    if getter is None:
        raise WorkflowError(f"Unknown action provider '{provider}'.", 500)
    return getter()


def _log_decision(action, decision: str) -> None:
    """Record the human decision only.

    Approving is not a provider write: logging it as a successful
    `create_event` call made the Activity Monitor claim writes that had not
    happened yet. Provider writes are logged by `execute_workflow` instead.
    """
    info = _provider_info(action.provider)
    log_activity(
        provider_type="workflow",
        provider_name="local-workflow-engine",
        operation="approval_decision",
        status="rejected" if decision == "reject" else "success",
        message=(
            f"Rejected by user: {action.title}"
            if decision == "reject"
            else f"Approved by user: {action.title} (not executed yet)"
        ),
        workflow_id=action.workflow_id,
        action_id=action.id,
        detail={
            "decision": decision,
            "target_provider": action.provider,
            "target_operation": action.action_type,
            "provider_kind": info.kind,
            "executed": False,
        },
        simulated=True,
    )


def decide_action(workflow_id: str, action_id: str, decision: str) -> Workflow:
    if decision not in {"approve", "reject"}:
        raise WorkflowError("Decision must be 'approve' or 'reject'.", 422)
    with get_db() as conn:
        workflow = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        if workflow is None:
            raise WorkflowError("Workflow not found.", 404)
        if workflow["status"] != "pending_approval":
            raise WorkflowError(
                f"This workflow is '{workflow['status']}' — decisions are closed.", 409
            )
        row = conn.execute(
            f"SELECT {ACTION_COLUMNS} FROM actions WHERE id = ? AND workflow_id = ?",
            (action_id, workflow_id),
        ).fetchone()
        if row is None:
            raise WorkflowError("Action not found in this workflow.", 404)
        if row["status"] != "proposed":
            raise WorkflowError(f"Action is already '{row['status']}' and cannot change.", 409)
        new_status = "approved" if decision == "approve" else "rejected"
        cursor = conn.execute(
            "UPDATE actions SET status = ?, updated_at = ? WHERE id = ? AND status = 'proposed'",
            (new_status, iso(now()), action_id),
        )
        if cursor.rowcount == 0:
            raise WorkflowError("Action was already decided.", 409)
        remaining = conn.execute(
            "SELECT COUNT(*) AS count FROM actions WHERE workflow_id = ? AND status = 'proposed'",
            (workflow_id,),
        ).fetchone()["count"]
        approved = conn.execute(
            "SELECT COUNT(*) AS count FROM actions WHERE workflow_id = ? AND status = 'approved'",
            (workflow_id,),
        ).fetchone()["count"]
        if remaining == 0 and approved == 0:
            conn.execute(
                "UPDATE workflows SET status = 'rejected', decided_at = ?, updated_at = ?, error = ? WHERE id = ?",
                (iso(now()), iso(now()), "All proposed actions were rejected.", workflow_id),
            )
    action = row_to_action(row)
    _log_decision(action, decision)
    return get_workflow(workflow_id)


def decide_all(workflow_id: str, decision: str, action_ids: list[str] | None = None) -> Workflow:
    if decision not in {"approve", "reject"}:
        raise WorkflowError("Decision must be 'approve' or 'reject'.", 422)
    with get_db() as conn:
        workflow = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        if workflow is None:
            raise WorkflowError("Workflow not found.", 404)
        if workflow["status"] != "pending_approval":
            raise WorkflowError(f"This workflow is '{workflow['status']}' — decisions are closed.", 409)
        action_rows = conn.execute(
            f"SELECT {ACTION_COLUMNS} FROM actions WHERE workflow_id = ? AND status = 'proposed'",
            (workflow_id,),
        ).fetchall()
    selected = [row for row in action_rows if not action_ids or row["id"] in set(action_ids)]
    if not selected:
        raise WorkflowError("No proposed actions match this decision.", 409)
    result = None
    for row in selected:
        result = decide_action(workflow_id, row["id"], decision)
    assert result is not None
    return result


def _claim_action(action_id: str) -> dict | None:
    """Atomically move approved -> executing. Returns the row if claimed."""
    stamp = iso(now())
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE actions SET status = 'executing', updated_at = ? WHERE id = ? AND status = 'approved'",
            (stamp, action_id),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(f"SELECT {ACTION_COLUMNS} FROM actions WHERE id = ?", (action_id,)).fetchone()
    return dict(row) if row else None


def _finish_action(action_id: str, *, status: str, result: dict | None = None, error: str = "") -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE actions SET status = ?, result = ?, error = ?, updated_at = ?, executed_at = ? WHERE id = ?",
            (status, dumps(result or {}), error, iso(now()), iso(now()), action_id),
        )


def _describe_event(title: str, start, end, time_format: str) -> str:
    return f"Created calendar event '{title}' ({fmt_time(start, time_format)}–{fmt_time(end, time_format)})."


def perform_action(action: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Execute one action through the active provider. Returns (result, message)."""
    services = get_services()
    settings = get_settings()
    time_format = str(settings.get("time_format", "24h"))
    payload = action["payload"]
    if isinstance(payload, str):  # defensive: row -> action conversion normally handles this
        import json

        payload = json.loads(payload)

    if action["action_type"] == "create_event":
        event = services.calendar.create_event(EventCreate(**payload), source="workflow")
        return (
            {"event_id": event.id, "event": event.model_dump(mode="json")},
            _describe_event(event.title, event.start_at, event.end_at, time_format),
        )
    if action["action_type"] == "create_task":
        task = services.tasks.create_task(TaskCreate(**payload))
        return ({"task_id": task.id, "task": task.model_dump(mode="json")}, f"Created task '{task.title}'.")
    if action["action_type"] == "create_reminder":
        reminder = services.reminders.create_reminder(ReminderCreate(**payload))
        return (
            {"reminder_id": reminder.id, "reminder": reminder.model_dump(mode="json")},
            f"Created reminder '{reminder.title}' for {reminder.remind_at.strftime('%d %b %H:%M')}.",
        )
    if action["action_type"] == "send_email":
        result = services.mail.send_email(EmailMessage(**payload))
        recipients = ", ".join(result.get("to") or [])
        return (result, f"Sent email '{result.get('subject', '')}' to {recipients}.")
    if action["action_type"] == "complete_task":
        task = services.tasks.update_task(payload["task_id"], TaskUpdate(**payload["update"]))
        return ({"task_id": task.id}, f"Marked task '{task.title}' as {task.status}.")
    if action["action_type"] == "dismiss_reminder":
        reminder = services.reminders.dismiss_reminder(payload["reminder_id"])
        return (
            {"reminder_id": reminder.id, "reminder": reminder.model_dump(mode="json")},
            f"Dismissed reminder '{reminder.title}'.",
        )
    raise WorkflowError(f"Unsupported action type '{action['action_type']}'.", 500)


def execute_workflow(workflow_id: str) -> Workflow:
    workflow = get_workflow(workflow_id)
    if workflow.status != "pending_approval":
        raise WorkflowError(
            f"This workflow is '{workflow.status}'. It cannot be executed again — duplicate execution is blocked.",
            409,
        )
    with get_db() as conn:
        approved = conn.execute(
            f"SELECT {ACTION_COLUMNS} FROM actions WHERE workflow_id = ? AND status = 'approved' ORDER BY order_index",
            (workflow_id,),
        ).fetchall()
    if not approved:
        raise WorkflowError("Approve at least one action before executing the workflow.", 400)

    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE workflows SET status = 'executing', decided_at = COALESCE(decided_at, ?), updated_at = ?"
            " WHERE id = ? AND status = 'pending_approval'",
            (iso(now()), iso(now()), workflow_id),
        )
        if cursor.rowcount == 0:
            raise WorkflowError("Workflow is no longer awaiting execution.", 409)

    executed = 0
    failures: list[str] = []
    for row in approved:
        action_id = row["id"]
        claimed = _claim_action(action_id)
        if claimed is None:
            continue  # another request already executed this action
        action = row_to_action(row)
        info = _provider_info(action.provider)
        try:
            result, message = perform_action(claimed)
        except Exception as exc:  # provider or validation failure
            failures.append(f"{action.title}: {exc}")
            _finish_action(action_id, status="failed", error=str(exc))
            log_activity(
                provider_type=action.provider,
                provider_name=info.key,
                operation=action.action_type,
                status="failed",
                message=f"Failed to {action.action_type.replace('_', ' ')}: {exc}",
                workflow_id=workflow_id,
                action_id=action_id,
                detail={"provider_kind": info.kind, "error": str(exc)},
                simulated=info.kind == "local",
            )
            continue
        _finish_action(action_id, status="executed", result=result)
        executed += 1
        log_activity(
            provider_type=action.provider,
            provider_name=info.key,
            operation=action.action_type,
            status="success",
            message=message,
            workflow_id=workflow_id,
            action_id=action_id,
            detail={
                "provider_kind": info.kind,
                "simulated": info.kind == "local",
                "result": result,
            },
            simulated=info.kind == "local",
        )

    # Actions the user never decided are closed out here. Leaving them as
    # 'proposed' inside a finished workflow stranded them forever, because
    # decisions are only accepted while the workflow is still pending.
    skipped = 0
    stamp = iso(now())
    with get_db() as conn:
        undecided = conn.execute(
            "SELECT id FROM actions WHERE workflow_id = ? AND status = 'proposed'",
            (workflow_id,),
        ).fetchall()
        for row in undecided:
            cursor = conn.execute(
                "UPDATE actions SET status = 'rejected', error = ?, updated_at = ?"
                " WHERE id = ? AND status = 'proposed'",
                ("Not approved when the workflow was executed.", stamp, row["id"]),
            )
            skipped += cursor.rowcount

    if executed and not failures:
        final_status = "completed"
    elif executed and failures:
        final_status = "partial"
    else:
        final_status = "failed"

    summary = {
        "executed": executed,
        "failed": len(failures),
        "skipped": skipped,
        "failures": failures,
        "status": final_status,
    }
    with get_db() as conn:
        conn.execute(
            "UPDATE workflows SET status = ?, result = ?, executed_at = ?, updated_at = ?, error = ? WHERE id = ?",
            (
                final_status,
                dumps(summary),
                iso(now()),
                iso(now()),
                "; ".join(failures) if failures else None,
                workflow_id,
            ),
        )

    log_activity(
        provider_type="workflow",
        provider_name="local-workflow-engine",
        operation="execute_workflow",
        status="success" if final_status == "completed" else "failed",
        message=(
            f"Workflow finished: {executed} action(s) executed"
            + (f", {len(failures)} failed." if failures else ".")
        ),
        workflow_id=workflow_id,
        detail=summary,
        simulated=True,
    )
    return get_workflow(workflow_id)
