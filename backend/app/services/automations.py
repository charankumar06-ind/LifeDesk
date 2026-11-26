"""Automation catalog with honest, provider-derived readiness.

The catalog is the product surface for the hackathon: every item maps to a
command the deterministic interpreter understands, and its status is computed
from the live provider boundary instead of being hardcoded in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..providers.registry import get_services


@dataclass(frozen=True)
class AutomationSpec:
    id: str
    title: str
    description: str
    category: str
    example: str
    action: str  # read | write
    capability: str  # calendar | tasks | reminders | mail | external
    planned: bool = False
    setup_note: str = ""


CATALOG: tuple[AutomationSpec, ...] = (
    AutomationSpec(
        id="plan_day",
        title="Plan my day",
        description="Rank open tasks, protect study time and propose focus blocks around existing events.",
        category="Daily planning",
        example="Plan my day. I have two pending assignments and need a two-hour Python study session.",
        action="write",
        capability="calendar",
    ),
    AutomationSpec(
        id="daily_briefing",
        title="Daily briefing",
        description="Read today's events, open and overdue tasks, and pending reminders in one read-only summary.",
        category="Daily planning",
        example="Give me my daily briefing",
        action="read",
        capability="calendar",
    ),
    AutomationSpec(
        id="find_free_time",
        title="Find free time",
        description="Scan the calendar for conflict-free gaps of a requested length inside your working window.",
        category="Focus & time",
        example="Find a free 90-minute slot tomorrow",
        action="read",
        capability="calendar",
    ),
    AutomationSpec(
        id="weekly_review",
        title="Weekly review",
        description="Summarize the last seven days: tasks completed and created, busy minutes, and what stays open.",
        category="Daily planning",
        example="Review my week",
        action="read",
        capability="tasks",
    ),
    AutomationSpec(
        id="schedule_event",
        title="Schedule a meeting",
        description="Create a calendar event with conflict detection and an approval preview.",
        category="Calendar",
        example="Schedule a meeting with the design team tomorrow at 15:00",
        action="write",
        capability="calendar",
    ),
    AutomationSpec(
        id="schedule_study",
        title="Schedule a study session",
        description="Reserve the first conflict-free block for a topic and duration you choose.",
        category="Focus & time",
        example="Schedule a two-hour Python study session",
        action="write",
        capability="calendar",
    ),
    AutomationSpec(
        id="create_task",
        title="Create a task",
        description="Turn a request into a prioritized task with an optional due date.",
        category="Tasks",
        example="Create a task to review lecture notes tomorrow",
        action="write",
        capability="tasks",
    ),
    AutomationSpec(
        id="list_pending",
        title="Show pending tasks",
        description="Return every open task with priority and due date; nothing is modified.",
        category="Tasks",
        example="Show pending tasks",
        action="read",
        capability="tasks",
    ),
    AutomationSpec(
        id="complete_task",
        title="Complete a task",
        description="Match an open task by title and propose marking it done for approval.",
        category="Tasks",
        example="Complete task review lecture notes",
        action="write",
        capability="tasks",
    ),
    AutomationSpec(
        id="create_reminder",
        title="Create a reminder",
        description="Propose a timed reminder that becomes active only after approval.",
        category="Reminders",
        example="Remind me to submit the course form at 17:00",
        action="write",
        capability="reminders",
    ),
    AutomationSpec(
        id="dismiss_reminder",
        title="Dismiss a reminder",
        description="Find a pending reminder by title and propose dismissing it.",
        category="Reminders",
        example="Dismiss the reminder about course form",
        action="write",
        capability="reminders",
    ),
    AutomationSpec(
        id="send_email",
        title="Send an email",
        description="Compose an outbound email; delivery happens only after approval and execute.",
        category="Communication",
        example="Send mail to friend@example.com saying HI",
        action="write",
        capability="mail",
    ),
    AutomationSpec(
        id="web_research",
        title="Web research",
        description="Search the web and return cited findings without leaving the workflow.",
        category="Research",
        example="Research the best MCP servers for calendar sync",
        action="read",
        capability="external",
        planned=True,
        setup_note="Planned: needs a search/browse MCP server and an API key.",
    ),
    AutomationSpec(
        id="weather_briefing",
        title="Weather in the briefing",
        description="Add tomorrow's forecast to the daily briefing before planning outdoor work.",
        category="Daily planning",
        example="Will it rain tomorrow?",
        action="read",
        capability="external",
        planned=True,
        setup_note="Planned: needs a weather MCP server or API key.",
    ),
    AutomationSpec(
        id="team_notification",
        title="Slack or Teams notification",
        description="Post the approved plan or a reminder to a team channel.",
        category="Communication",
        example="Notify the team channel about today's plan",
        action="write",
        capability="external",
        planned=True,
        setup_note="Planned: needs a Slack/Teams MCP server and workspace authorization.",
    ),
    AutomationSpec(
        id="drive_search",
        title="Find a file in Drive",
        description="Search connected cloud storage and attach the matching document to a task.",
        category="Files",
        example="Find the project brief in my Google Drive",
        action="read",
        capability="external",
        planned=True,
        setup_note="Planned: needs a Google Drive/Dropbox MCP server with OAuth.",
    ),
)

_CAPABILITY_PROVIDER = {
    "calendar": "calendar",
    "tasks": "tasks",
    "reminders": "reminders",
}


def _provider_status(services, capability: str) -> tuple[str, str]:
    info = getattr(services, _CAPABILITY_PROVIDER[capability]).info
    if info.status == "connected":
        return "ready", f"Runs through {info.label} ({info.transport})."
    if info.status == "not_configured":
        return "needs_setup", info.note
    return "degraded", info.note or "The provider is reporting an error."


def automation_catalog() -> dict:
    services = get_services()
    runtime = services.runtime or {}
    mcp_degraded = services.mode == "mcp" and runtime.get("status") == "error"
    items: list[dict] = []

    for spec in CATALOG:
        if spec.planned:
            status = "planned"
            detail = spec.setup_note
        elif mcp_degraded and spec.capability != "external":
            status = "degraded"
            detail = (
                "The last MCP call failed, so this automation is paused until a later "
                "call succeeds. No local fallback is active."
            )
        elif spec.capability == "mail":
            mail_available = bool(runtime.get("mail_available"))
            if services.mode != "mcp":
                status = "needs_setup"
                detail = "Local mode never sends email. Switch to MCP mode and configure SMTP."
            elif not mail_available:
                status = "needs_setup"
                detail = "The connected MCP server does not expose the optional mail_send tool."
            elif runtime.get("mail_configured"):
                status = "ready"
                detail = "SMTP is configured on the MCP server; delivery still requires approval."
            else:
                status = "needs_setup"
                detail = (
                    "The MCP mail tool is connected but SMTP credentials are missing. "
                    "Set LIFEDESK_SMTP_USER and LIFEDESK_SMTP_PASSWORD on the server."
                )
        elif spec.capability in _CAPABILITY_PROVIDER:
            status, detail = _provider_status(services, spec.capability)
        else:
            status = "planned"
            detail = spec.setup_note or "Planned external capability."

        items.append(
            {
                "id": spec.id,
                "title": spec.title,
                "description": spec.description,
                "category": spec.category,
                "example": spec.example,
                "action": spec.action,
                "capability": spec.capability,
                "planned": spec.planned,
                "status": status,
                "status_detail": detail,
            }
        )

    total = len(items)
    ready = sum(1 for item in items if item["status"] == "ready")
    needs_setup = sum(1 for item in items if item["status"] == "needs_setup")
    planned = sum(1 for item in items if item["status"] == "planned")
    degraded = sum(1 for item in items if item["status"] == "degraded")
    return {
        "items": items,
        "summary": {
            "total": total,
            "ready": ready,
            "needs_setup": needs_setup,
            "planned": planned,
            "degraded": degraded,
            "implemented": total - planned,
            "working_percentage": round(ready / total * 100) if total else 0,
            "implemented_percentage": round((total - planned) / total * 100) if total else 0,
        },
        "provider_mode": services.mode,
    }
