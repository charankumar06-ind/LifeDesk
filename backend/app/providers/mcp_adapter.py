"""MCP providers behind the same interfaces as the local SQLite providers.

The tool contract is intentionally small and explicit. It is implemented by the
bundled reference server in `backend/mcp_server/server.py`; an external MCP
bridge can implement the same contract if it wants LifeDesk to use it.

    calendar_list_events   {start, end}
    calendar_get_event     {event_id}
    calendar_create_event  EventCreate fields + source
    calendar_update_event  {event_id, fields}
    calendar_delete_event  {event_id}
    tasks_list             {status?, priority?, search?}
    tasks_get              {task_id}
    tasks_create           TaskCreate fields
    tasks_update           {task_id, fields}
    tasks_delete           {task_id}
    reminders_list         {status?}
    reminders_create       ReminderCreate fields
    reminders_dismiss      {reminder_id}
    mail_send              {to, subject, body}  (optional)
    lifedesk_status        {}
    mail_status            {}  (optional)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from ..config import (
    BACKEND_DIR,
    MCP_ARGS_RAW,
    MCP_COMMAND,
    MCP_CWD,
    MCP_ENV_RAW,
    MCP_FALLBACK,
    MCP_HEADERS_RAW,
    MCP_LABEL,
    MCP_TIMEOUT,
    MCP_TRANSPORT,
    MCP_URL,
)
from ..domain import (
    EmailMessage,
    Event,
    EventCreate,
    EventUpdate,
    Reminder,
    ReminderCreate,
    Task,
    TaskCreate,
    TaskUpdate,
)
from ..utils import iso, now
from .base import (
    CalendarProvider,
    MailProvider,
    ProviderError,
    ProviderInfo,
    ProviderNotConfigured,
    ReminderProvider,
    TaskProvider,
)
from .mcp_client import McpClient, McpSettings

REQUIRED_TOOLS = frozenset(
    {
        "calendar_list_events",
        "calendar_get_event",
        "calendar_create_event",
        "calendar_update_event",
        "calendar_delete_event",
        "tasks_list",
        "tasks_get",
        "tasks_create",
        "tasks_update",
        "tasks_delete",
        "reminders_list",
        "reminders_create",
        "reminders_dismiss",
    }
)

#: Email is an optional capability: a server without it still starts and serves
#: calendar/tasks/reminders, and reports email as unavailable.
MAIL_TOOL = "mail_send"

_runtime: dict[str, Any] = {
    "requested": False,
    "configured": False,
    "transport": MCP_TRANSPORT,
    "endpoint": "",
    "status": "not_requested",
    "fallback_active": False,
    "error": None,
    "tools": [],
    "required_tools": sorted(REQUIRED_TOOLS),
    "mail_available": False,
    "mail_configured": None,
    "checked_at": None,
}


def mcp_fallback_mode() -> str:
    return os.environ.get("LIFEDESK_MCP_FALLBACK", MCP_FALLBACK).strip().lower()


def get_mcp_runtime() -> dict[str, Any]:
    return dict(_runtime)


def _mark_failure(exc: ProviderError) -> None:
    """Degrade runtime health after a failed MCP call.

    This never changes provider selection: MCP mode stays fail-closed (HTTP 503)
    so a failure cannot be silently written to local SQLite.
    """
    _runtime.update(
        {
            "status": "error",
            "error": str(exc),
            "checked_at": iso(now()),
        }
    )


def _mark_success() -> None:
    """Recover runtime health on the next successful MCP call."""
    if _runtime.get("status") == "connected":
        return
    _runtime.update(
        {
            "status": "connected",
            "error": None,
            "checked_at": iso(now()),
        }
    )


def _call(client: McpClient, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call an MCP tool while keeping the reported runtime health current."""
    try:
        result = client.call_tool(tool, arguments or {})
    except ProviderError as exc:
        _mark_failure(exc)
        raise
    _mark_success()
    return result


def _json_env(name: str, raw: str | None, expected: type) -> Any:
    if not raw:
        return expected()
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise ProviderNotConfigured(f"{name} must be valid JSON: {exc}") from exc
    if not isinstance(value, expected):
        raise ProviderNotConfigured(f"{name} must be a JSON {expected.__name__}.")
    return value


def _settings_from_env() -> McpSettings:
    transport = MCP_TRANSPORT
    if transport not in {"stdio", "http"}:
        raise ProviderNotConfigured(
            "LIFEDESK_MCP_TRANSPORT must be 'stdio' or 'http'."
        )

    if MCP_ARGS_RAW:
        args = _json_env("LIFEDESK_MCP_ARGS", MCP_ARGS_RAW, list)
        if not all(isinstance(item, str) for item in args):
            raise ProviderNotConfigured("LIFEDESK_MCP_ARGS must contain only strings.")
        args = tuple(args)
    else:
        args = ("-m", "mcp_server.server")

    env = _json_env("LIFEDESK_MCP_ENV", MCP_ENV_RAW, dict)
    headers = _json_env("LIFEDESK_MCP_HEADERS", MCP_HEADERS_RAW, dict)
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in env.items()):
        raise ProviderNotConfigured("LIFEDESK_MCP_ENV must map names to string values.")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in headers.items()):
        raise ProviderNotConfigured("LIFEDESK_MCP_HEADERS must map names to string values.")

    if transport == "http":
        if not MCP_URL:
            raise ProviderNotConfigured(
                "LIFEDESK_MCP_URL is required when LIFEDESK_MCP_TRANSPORT=http."
            )
        command = ""
        cwd = None
        label = MCP_LABEL or "External MCP server"
    else:
        if not MCP_COMMAND:
            raise ProviderNotConfigured(
                "LIFEDESK_MCP_COMMAND is required when LIFEDESK_MCP_TRANSPORT=stdio."
            )
        command = MCP_COMMAND
        cwd = MCP_CWD or str(BACKEND_DIR)
        label = MCP_LABEL or "LifeDesk reference MCP server"

    return McpSettings(
        transport=transport,
        command=command,
        args=args,
        cwd=cwd,
        env=env,
        url=MCP_URL or None,
        headers=headers,
        timeout=max(1.0, float(MCP_TIMEOUT)),
        label=label,
    )


def _provider_info(kind: str, settings: McpSettings) -> ProviderInfo:
    labels = {
        "calendar": "MCP Calendar",
        "tasks": "MCP Tasks",
        "reminders": "MCP Reminders",
        "mail": "MCP Mail",
    }
    bundled = settings.transport == "stdio" and settings.label == "LifeDesk reference MCP server"
    if kind == "mail":
        note = (
            "Sends email through the bundled reference server over SMTP using its "
            "LIFEDESK_SMTP_* environment settings. Credentials never reach the browser."
            if bundled
            else (
                f"Sends email through {settings.endpoint_label()} over {settings.transport}. "
                "SMTP credentials are owned by that MCP server."
            )
        )
    else:
        note = (
            "Connected to the bundled reference server over stdio. Tool calls use the MCP "
            "protocol; the reference server stores data in the configured LifeDesk SQLite database."
            if bundled
            else (
                f"Connected to {settings.endpoint_label()} over {settings.transport}. "
                "Tool calls and external credentials are owned by that MCP server."
            )
        )
    return ProviderInfo(
        key=f"mcp-{kind}",
        label=labels[kind],
        kind="mcp",
        transport=settings.transport,
        status="connected",
        note=note,
    )


def _unavailable_mail_info(settings: McpSettings) -> ProviderInfo:
    return ProviderInfo(
        key="mcp-mail",
        label="MCP Mail (unavailable)",
        kind="mcp",
        transport=settings.transport,
        status="not_configured",
        note=(
            "The configured MCP server does not expose the optional mail_send tool. "
            "Email actions fail without affecting calendar, task or reminder calls."
        ),
    )


class McpCalendarProvider(CalendarProvider):
    def __init__(self, client: McpClient, info: ProviderInfo):
        self._client = client
        self.info = info

    def list_events(self, start: datetime, end: datetime) -> list[Event]:
        result = _call(
            self._client,
            "calendar_list_events",
            {"start": iso(start), "end": iso(end)},
        )
        rows = result.get("events") or []
        return [Event.model_validate(row) for row in rows]

    def get_event(self, event_id: str) -> Event | None:
        result = _call(self._client, "calendar_get_event", {"event_id": event_id})
        row = result.get("event")
        return Event.model_validate(row) if row else None

    def create_event(self, data: EventCreate, source: str = "mcp") -> Event:
        arguments = data.model_dump(mode="json")
        arguments["source"] = source
        result = _call(self._client, "calendar_create_event", arguments)
        row = result.get("event")
        if not row:
            raise ProviderError("MCP calendar server returned no event after create.")
        return Event.model_validate(row)

    def update_event(self, event_id: str, data: EventUpdate) -> Event:
        fields = data.model_dump(exclude_unset=True, mode="json")
        if not fields:
            existing = self.get_event(event_id)
            if existing is None:
                raise KeyError(event_id)
            return existing
        result = _call(
            self._client,
            "calendar_update_event",
            {"event_id": event_id, "fields": fields},
        )
        row = result.get("event")
        if not row:
            raise KeyError(event_id)
        return Event.model_validate(row)

    def delete_event(self, event_id: str) -> None:
        result = _call(self._client, "calendar_delete_event", {"event_id": event_id})
        if not result.get("deleted"):
            raise KeyError(event_id)


class McpTaskProvider(TaskProvider):
    def __init__(self, client: McpClient, info: ProviderInfo):
        self._client = client
        self.info = info

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
    ) -> list[Task]:
        arguments = {
            key: value
            for key, value in {"status": status, "priority": priority, "search": search}.items()
            if value is not None
        }
        result = _call(self._client, "tasks_list", arguments)
        rows = result.get("tasks") or []
        return [Task.model_validate(row) for row in rows]

    def get_task(self, task_id: str) -> Task | None:
        result = _call(self._client, "tasks_get", {"task_id": task_id})
        row = result.get("task")
        return Task.model_validate(row) if row else None

    def create_task(self, data: TaskCreate) -> Task:
        result = _call(self._client, "tasks_create", data.model_dump(mode="json"))
        row = result.get("task")
        if not row:
            raise ProviderError("MCP task server returned no task after create.")
        return Task.model_validate(row)

    def update_task(self, task_id: str, data: TaskUpdate) -> Task:
        fields = data.model_dump(exclude_unset=True, mode="json")
        if not fields:
            existing = self.get_task(task_id)
            if existing is None:
                raise KeyError(task_id)
            return existing
        result = _call(self._client, "tasks_update", {"task_id": task_id, "fields": fields})
        row = result.get("task")
        if not row:
            raise KeyError(task_id)
        return Task.model_validate(row)

    def delete_task(self, task_id: str) -> None:
        result = _call(self._client, "tasks_delete", {"task_id": task_id})
        if not result.get("deleted"):
            raise KeyError(task_id)


class McpMailProvider(MailProvider):
    def __init__(self, client: McpClient, info: ProviderInfo):
        self._client = client
        self.info = info

    def send_email(self, message: EmailMessage) -> dict:
        result = _call(
            self._client,
            "mail_send",
            {"to": message.to, "subject": message.subject, "body": message.body},
        )
        if not result.get("sent"):
            raise ProviderError("MCP mail server did not confirm delivery.")
        return result


class UnavailableMailProvider(MailProvider):
    """Email capability for an MCP server that does not implement mail_send."""

    def __init__(self, info: ProviderInfo):
        self.info = info

    def send_email(self, message: EmailMessage) -> dict:
        raise ProviderError(
            "The configured MCP server does not expose the optional mail_send tool, "
            "so email is unavailable. No message was sent."
        )


class McpReminderProvider(ReminderProvider):
    def __init__(self, client: McpClient, info: ProviderInfo):
        self._client = client
        self.info = info

    def list_reminders(self, *, status: str | None = None) -> list[Reminder]:
        arguments = {"status": status} if status else {}
        result = _call(self._client, "reminders_list", arguments)
        rows = result.get("reminders") or []
        return [Reminder.model_validate(row) for row in rows]

    def create_reminder(self, data: ReminderCreate) -> Reminder:
        result = _call(self._client, "reminders_create", data.model_dump(mode="json"))
        row = result.get("reminder")
        if not row:
            raise ProviderError("MCP reminder server returned no reminder after create.")
        return Reminder.model_validate(row)

    def dismiss_reminder(self, reminder_id: str) -> Reminder:
        result = _call(self._client, "reminders_dismiss", {"reminder_id": reminder_id})
        row = result.get("reminder")
        if not row:
            raise KeyError(reminder_id)
        return Reminder.model_validate(row)


def build_mcp_services():
    """Connect to the configured MCP server and build provider instances.

    Raises `ProviderNotConfigured` when the server cannot be reached or does not
    expose the required tool contract. `registry.build_services` decides whether
    to fall back to local providers.
    """
    global _runtime
    _runtime = {
        "requested": True,
        "configured": False,
        "transport": MCP_TRANSPORT,
        "endpoint": "",
        "status": "error",
        "fallback_active": mcp_fallback_mode() == "local",
        "error": None,
        "tools": [],
        "required_tools": sorted(REQUIRED_TOOLS),
        "mail_available": False,
        "mail_configured": None,
        "checked_at": None,
    }

    try:
        settings = _settings_from_env()
    except ProviderNotConfigured as exc:
        _runtime["error"] = str(exc)
        raise

    _runtime.update(
        {
            "configured": True,
            "transport": settings.transport,
            "endpoint": settings.endpoint_label(),
        }
    )
    client = McpClient(settings)
    try:
        tools = client.probe()
    except ProviderError as exc:
        _runtime["error"] = str(exc)
        raise ProviderNotConfigured(str(exc)) from exc

    tool_names = set(tools)
    missing = sorted(REQUIRED_TOOLS - tool_names)
    if missing:
        message = (
            "MCP server is missing required tools: " + ", ".join(missing) + "."
        )
        _runtime["error"] = message
        raise ProviderNotConfigured(message)

    mail_available = MAIL_TOOL in tool_names
    mail_configured: bool | None = None
    if mail_available and "mail_status" in tool_names:
        try:
            mail_configured = bool(client.call_tool("mail_status").get("configured"))
        except ProviderError:
            mail_configured = None

    _runtime.update(
        {
            "status": "connected",
            "fallback_active": False,
            "error": None,
            "tools": sorted(tools),
            "mail_available": mail_available,
            "mail_configured": mail_configured if mail_available else None,
            "checked_at": iso(now()),
        }
    )

    from .registry import Services  # local import avoids a circular import

    return Services(
        calendar=McpCalendarProvider(client, _provider_info("calendar", settings)),
        tasks=McpTaskProvider(client, _provider_info("tasks", settings)),
        reminders=McpReminderProvider(client, _provider_info("reminders", settings)),
        mail=(
            McpMailProvider(client, _provider_info("mail", settings))
            if mail_available
            else UnavailableMailProvider(_unavailable_mail_info(settings))
        ),
        mode="mcp",
        # Shared by reference: runtime health changes made by tool calls are
        # visible to /api/system without rebuilding the services.
        runtime=_runtime,
    )
