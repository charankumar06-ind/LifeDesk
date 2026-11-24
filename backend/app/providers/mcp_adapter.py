"""MCP provider integration boundary (intentionally not implemented yet).

No MCP server is running in this prototype and nothing here pretends otherwise.
The classes below document exactly what the 24-hour hackathon needs to fill in.
They implement the same interfaces as the local providers, so the workflow
engine does not change when they are completed.

Planned mapping (official Python MCP SDK, `mcp` package):

    CalendarProvider.list_events(start, end)  -> tool "calendar.list_events"
    CalendarProvider.create_event(data)       -> tool "calendar.create_event"
    CalendarProvider.update_event(id, data)   -> tool "calendar.update_event"
    CalendarProvider.delete_event(id)         -> tool "calendar.delete_event"
    TaskProvider.list_tasks(...)              -> tool "tasks.list"
    TaskProvider.create_task(data)            -> tool "tasks.create"
    TaskProvider.update_task(id, data)        -> tool "tasks.update"
    TaskProvider.delete_task(id)              -> tool "tasks.delete"
    ReminderProvider.create_reminder(data)    -> tool "reminders.create"

Implementation steps during the hackathon:
1. Add `mcp` to requirements and configure server URLs/credentials via env vars
   (never in the repo).
2. Create an `McpClient` wrapper around `mcp.client.stdio`/`streamablehttp` that
   opens a session and calls tools, mapping results into `domain.py` models.
3. Fill in the provider methods below; raise `ProviderError` on tool failures.
4. Set LIFEDESK_PROVIDER_MODE=mcp. `registry.build_services` will pick these up.
"""

from __future__ import annotations

from datetime import datetime

from ..domain import Event, EventCreate, EventUpdate, Reminder, ReminderCreate, Task, TaskCreate, TaskUpdate
from .base import CalendarProvider, ProviderInfo, ProviderNotConfigured, ReminderProvider, TaskProvider


def _unconfigured(name: str) -> ProviderNotConfigured:
    return ProviderNotConfigured(
        f"{name} is not configured. This build runs local SQLite providers "
        "(Demo Mode — Local Data). Connect an MCP server and register the provider "
        "in app/providers/mcp_adapter.py to enable it."
    )


MCP_CALENDAR_INFO = ProviderInfo(
    key="mcp-calendar",
    label="MCP Calendar",
    kind="mcp",
    transport="stdio / streamable-http",
    status="not_configured",
    note="Boundary ready. Requires an MCP server URL and tool contract.",
)

MCP_TASKS_INFO = ProviderInfo(
    key="mcp-tasks",
    label="MCP Tasks",
    kind="mcp",
    transport="stdio / streamable-http",
    status="not_configured",
    note="Boundary ready. Requires an MCP server URL and tool contract.",
)

MCP_REMINDERS_INFO = ProviderInfo(
    key="mcp-reminders",
    label="MCP Reminders",
    kind="mcp",
    transport="stdio / streamable-http",
    status="not_configured",
    note="Boundary ready. Requires an MCP server URL and tool contract.",
)


class McpCalendarProvider(CalendarProvider):
    info = MCP_CALENDAR_INFO

    def list_events(self, start: datetime, end: datetime) -> list[Event]:
        raise _unconfigured("MCP calendar provider")

    def get_event(self, event_id: str) -> Event | None:
        raise _unconfigured("MCP calendar provider")

    def create_event(self, data: EventCreate, source: str = "mcp") -> Event:
        raise _unconfigured("MCP calendar provider")

    def update_event(self, event_id: str, data: EventUpdate) -> Event:
        raise _unconfigured("MCP calendar provider")

    def delete_event(self, event_id: str) -> None:
        raise _unconfigured("MCP calendar provider")


class McpTaskProvider(TaskProvider):
    info = MCP_TASKS_INFO

    def list_tasks(self, *, status: str | None = None, priority: str | None = None,
                   search: str | None = None) -> list[Task]:
        raise _unconfigured("MCP task provider")

    def get_task(self, task_id: str) -> Task | None:
        raise _unconfigured("MCP task provider")

    def create_task(self, data: TaskCreate) -> Task:
        raise _unconfigured("MCP task provider")

    def update_task(self, task_id: str, data: TaskUpdate) -> Task:
        raise _unconfigured("MCP task provider")

    def delete_task(self, task_id: str) -> None:
        raise _unconfigured("MCP task provider")


class McpReminderProvider(ReminderProvider):
    info = MCP_REMINDERS_INFO

    def list_reminders(self, *, status: str | None = None) -> list[Reminder]:
        raise _unconfigured("MCP reminder provider")

    def create_reminder(self, data: ReminderCreate) -> Reminder:
        raise _unconfigured("MCP reminder provider")

    def dismiss_reminder(self, reminder_id: str) -> Reminder:
        raise _unconfigured("MCP reminder provider")


def build_mcp_services():
    """Wire MCP providers here once servers exist.

    Fail fast (rather than silently falling back to local data) so a
    misconfigured demo is obvious instead of misleading.
    """
    raise ProviderNotConfigured(
        "MCP provider mode is not configured in this build. "
        "Set LIFEDESK_PROVIDER_MODE=local to use the SQLite demo providers."
    )
