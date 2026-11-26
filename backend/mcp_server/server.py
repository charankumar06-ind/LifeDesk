"""LifeDesk reference MCP server (stdio or streamable HTTP).

This is a real MCP server: it exposes the tool contract in
`app/providers/mcp_adapter.py` and is discoverable with `tools/list`. It is
deliberately small and credential-free so MCP mode can be exercised locally.
Its storage is the same SQLite database as the rest of LifeDesk, which makes
switching provider modes easy to demo.

For an external calendar (Google/Outlook), run a bridge that implements the
same tools and let that bridge own OAuth. LifeDesk never handles those
credentials in this prototype.
"""

from __future__ import annotations

import os
import re
import smtplib
import uuid
from datetime import datetime
from email.message import EmailMessage as SmtpMessage
from email.utils import parseaddr
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.db import get_db, init_db
from app.domain import EventCreate, EventUpdate, ReminderCreate, TaskCreate, TaskUpdate
from app.providers.local_calendar import LocalCalendarProvider
from app.providers.local_reminder import LocalReminderProvider
from app.providers.local_task import LocalTaskProvider

mcp = FastMCP(
    "lifedesk-reference",
    instructions=(
        "Local LifeDesk calendar, task, reminder and email tools. Every write is made "
        "only after the LifeDesk user approves a proposed workflow action. Email is "
        "delivered over SMTP using this server's LIFEDESK_SMTP_* environment settings."
    ),
    log_level="ERROR",
)

_calendar = LocalCalendarProvider()
_tasks = LocalTaskProvider()
_reminders = LocalReminderProvider()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _dump(model) -> dict[str, Any]:
    return model.model_dump(mode="json")


@mcp.tool()
def lifedesk_status() -> dict[str, Any]:
    """Report the reference server's storage and current row counts."""
    with get_db() as conn:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            for table in ("events", "tasks", "reminders")
        }
    return {
        "server": "lifedesk-reference",
        "storage": "sqlite",
        "counts": counts,
    }


@mcp.tool()
def calendar_list_events(start: str, end: str) -> dict[str, Any]:
    """List calendar events overlapping the [start, end) ISO-8601 interval."""
    events = _calendar.list_events(_dt(start), _dt(end))
    return {"events": [_dump(event) for event in events]}


@mcp.tool()
def calendar_get_event(event_id: str) -> dict[str, Any]:
    """Return one calendar event by id, or null when it does not exist."""
    event = _calendar.get_event(event_id)
    return {"event": _dump(event) if event else None}


@mcp.tool()
def calendar_create_event(
    title: str,
    start_at: str,
    end_at: str,
    description: str = "",
    location: str = "",
    kind: str = "meeting",
    source: str = "mcp",
) -> dict[str, Any]:
    """Create a calendar event and return it."""
    event = _calendar.create_event(
        EventCreate(
            title=title,
            start_at=_dt(start_at),
            end_at=_dt(end_at),
            description=description,
            location=location,
            kind=kind,
        ),
        source=source,
    )
    return {"event": _dump(event)}


@mcp.tool()
def calendar_update_event(event_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Patch a calendar event with the supplied fields; null event means not found."""
    try:
        event = _calendar.update_event(event_id, EventUpdate(**fields))
    except KeyError:
        return {"event": None}
    return {"event": _dump(event)}


@mcp.tool()
def calendar_delete_event(event_id: str) -> dict[str, Any]:
    """Delete a calendar event; returns deleted=false when it does not exist."""
    try:
        _calendar.delete_event(event_id)
    except KeyError:
        return {"deleted": False}
    return {"deleted": True}


@mcp.tool()
def tasks_list(
    status: str | None = None,
    priority: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """List tasks with optional status, priority and text filters."""
    tasks = _tasks.list_tasks(status=status, priority=priority, search=search)
    return {"tasks": [_dump(task) for task in tasks]}


@mcp.tool()
def tasks_get(task_id: str) -> dict[str, Any]:
    """Return one task by id, or null when it does not exist."""
    task = _tasks.get_task(task_id)
    return {"task": _dump(task) if task else None}


@mcp.tool()
def tasks_create(
    title: str,
    description: str = "",
    status: str = "todo",
    priority: str = "medium",
    due_at: str | None = None,
    estimate_minutes: int = 60,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create a task and return it."""
    task = _tasks.create_task(
        TaskCreate(
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_at=_dt(due_at) if due_at else None,
            estimate_minutes=estimate_minutes,
            tags=tags or [],
        )
    )
    return {"task": _dump(task)}


@mcp.tool()
def tasks_update(task_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Patch a task with the supplied fields; null task means not found."""
    try:
        task = _tasks.update_task(task_id, TaskUpdate(**fields))
    except KeyError:
        return {"task": None}
    return {"task": _dump(task)}


@mcp.tool()
def tasks_delete(task_id: str) -> dict[str, Any]:
    """Delete a task; returns deleted=false when it does not exist."""
    try:
        _tasks.delete_task(task_id)
    except KeyError:
        return {"deleted": False}
    return {"deleted": True}


@mcp.tool()
def reminders_list(status: str | None = None) -> dict[str, Any]:
    """List reminders, optionally filtered by pending/dismissed status."""
    reminders = _reminders.list_reminders(status=status)
    return {"reminders": [_dump(reminder) for reminder in reminders]}


@mcp.tool()
def reminders_create(title: str, remind_at: str, note: str = "") -> dict[str, Any]:
    """Create a reminder and return it."""
    reminder = _reminders.create_reminder(
        ReminderCreate(title=title, note=note, remind_at=_dt(remind_at))
    )
    return {"reminder": _dump(reminder)}


@mcp.tool()
def reminders_dismiss(reminder_id: str) -> dict[str, Any]:
    """Dismiss a reminder; null reminder means not found."""
    try:
        reminder = _reminders.dismiss_reminder(reminder_id)
    except KeyError:
        return {"reminder": None}
    return {"reminder": _dump(reminder)}


EMAIL_ADDRESS = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _smtp_config() -> tuple[str, int, str, str, str, bool, bool]:
    """Read SMTP settings from the server environment (never from LifeDesk DB)."""
    host = os.environ.get("LIFEDESK_SMTP_HOST", "smtp.gmail.com").strip() or "smtp.gmail.com"
    try:
        port = int(os.environ.get("LIFEDESK_SMTP_PORT", "587"))
    except ValueError as exc:
        raise RuntimeError("LIFEDESK_SMTP_PORT must be a number.") from exc
    user = os.environ.get("LIFEDESK_SMTP_USER", "").strip()
    password = os.environ.get("LIFEDESK_SMTP_PASSWORD", "")
    if not user or not password:
        raise RuntimeError(
            "Email is not configured on this MCP server. Set LIFEDESK_SMTP_USER and "
            "LIFEDESK_SMTP_PASSWORD (Gmail requires an App Password, not the account "
            "password) and restart the server."
        )
    # Gmail displays app passwords with spaces; the SMTP secret itself has none.
    if host.endswith("gmail.com"):
        password = password.replace(" ", "")
    from_addr = os.environ.get("LIFEDESK_SMTP_FROM", "").strip() or user
    use_ssl = port == 465 or os.environ.get("LIFEDESK_SMTP_SSL", "0").strip() == "1"
    starttls = not use_ssl and os.environ.get("LIFEDESK_SMTP_STARTTLS", "1").strip() != "0"
    return host, port, user, password, from_addr, use_ssl, starttls


@mcp.tool()
def mail_status() -> dict[str, Any]:
    """Report whether SMTP delivery is configured. Never returns credentials."""
    host = os.environ.get("LIFEDESK_SMTP_HOST", "smtp.gmail.com").strip() or "smtp.gmail.com"
    user = os.environ.get("LIFEDESK_SMTP_USER", "").strip()
    configured = bool(user and os.environ.get("LIFEDESK_SMTP_PASSWORD", ""))
    return {
        "configured": configured,
        "transport": "smtp",
        "host": host,
        "from": os.environ.get("LIFEDESK_SMTP_FROM", "").strip() or user,
    }


@mcp.tool()
def mail_send(to: list[str], subject: str, body: str) -> dict[str, Any]:
    """Send one email over SMTP and return delivery metadata."""
    recipients: list[str] = []
    for raw in to:
        address = (parseaddr(raw)[1] or "").strip()
        if not EMAIL_ADDRESS.match(address):
            raise RuntimeError(f"Invalid email address: {raw}")
        if address not in recipients:
            recipients.append(address)
    if not recipients:
        raise RuntimeError("At least one recipient address is required.")
    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject or not body:
        raise RuntimeError("Subject and body cannot be empty.")
    if len(subject) > 200 or len(body) > 20000:
        raise RuntimeError("Subject or body exceeds the allowed length.")

    host, port, user, password, from_addr, use_ssl, starttls = _smtp_config()
    message = SmtpMessage()
    message["From"] = from_addr
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message["Message-ID"] = f"<{uuid.uuid4().hex}@lifedesk.local>"
    message.set_content(body)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
                smtp.login(user, password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                smtp.ehlo()
                if starttls:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(user, password)
                smtp.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            "SMTP authentication failed. For Gmail, create an App Password and use it "
            "as LIFEDESK_SMTP_PASSWORD (2-Step Verification must be on)."
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise RuntimeError(f"SMTP delivery failed: {exc}") from exc

    return {
        "sent": True,
        "message_id": message["Message-ID"],
        "to": recipients,
        "subject": subject,
        "server": host,
    }


def main() -> None:
    init_db()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
