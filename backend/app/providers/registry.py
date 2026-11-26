"""Provider composition root.

This module is the single place that knows *which* implementations are active.
`LIFEDESK_PROVIDER_MODE=mcp` builds MCP-backed providers; `local` keeps the
SQLite demo providers. If MCP startup fails, `LIFEDESK_MCP_FALLBACK=local`
lets the app run on the local providers and reports `local-fallback` truthfully.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import PROVIDER_MODE
from .base import (
    CalendarProvider,
    MailProvider,
    ProviderInfo,
    ProviderNotConfigured,
    ReminderProvider,
    TaskProvider,
)
from .local_calendar import LocalCalendarProvider
from .local_mail import LocalMailProvider
from .local_reminder import LocalReminderProvider
from .local_task import LocalTaskProvider


@dataclass
class Services:
    calendar: CalendarProvider
    tasks: TaskProvider
    reminders: ReminderProvider
    mail: MailProvider
    mode: str
    runtime: dict = field(default_factory=dict)

    def provider_infos(self) -> list[dict]:
        return [
            info.__dict__
            for info in (
                self.calendar.info,
                self.tasks.info,
                self.reminders.info,
                self.mail.info,
            )
        ]


_services: Services | None = None


def build_local_services(mode: str = "local", runtime: dict | None = None) -> Services:
    return Services(
        calendar=LocalCalendarProvider(),
        tasks=LocalTaskProvider(),
        reminders=LocalReminderProvider(),
        mail=LocalMailProvider(),
        mode=mode,
        runtime=dict(runtime or {}),
    )


def build_services(mode: str | None = None) -> Services:
    mode = (mode or PROVIDER_MODE).lower()
    if mode == "mcp":
        from .mcp_adapter import build_mcp_services, get_mcp_runtime, mcp_fallback_mode

        try:
            return build_mcp_services()
        except ProviderNotConfigured as exc:
            runtime = get_mcp_runtime()
            if mcp_fallback_mode() != "local":
                raise
            runtime["fallback_active"] = True
            runtime["error"] = runtime.get("error") or str(exc)
            return build_local_services(mode="local-fallback", runtime=runtime)
    if mode != "local":
        raise ProviderNotConfigured(f"Unknown provider mode '{mode}'. Use 'local' or 'mcp'.")
    return build_local_services()


def get_services() -> Services:
    global _services
    if _services is None:
        _services = build_services()
    return _services


def set_services(services: Services) -> None:
    """Test/DI hook."""
    global _services
    _services = services


def reset_services() -> None:
    global _services
    _services = None


def provider_info_list() -> list[ProviderInfo]:
    services = get_services()
    return [services.calendar.info, services.tasks.info, services.reminders.info, services.mail.info]
