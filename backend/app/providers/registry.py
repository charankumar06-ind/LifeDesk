"""Provider composition root.

This module is the single place that knows *which* implementations are active.
During the hackathon, swap `build_local_services()` for an MCP-backed builder
(e.g. `build_mcp_services(calendar_url, tasks_url)`) and every workflow, API
route and UI screen keeps working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import PROVIDER_MODE
from .base import CalendarProvider, ProviderInfo, ProviderNotConfigured, ReminderProvider, TaskProvider
from .local_calendar import LocalCalendarProvider
from .local_reminder import LocalReminderProvider
from .local_task import LocalTaskProvider


@dataclass
class Services:
    calendar: CalendarProvider
    tasks: TaskProvider
    reminders: ReminderProvider
    mode: str

    def provider_infos(self) -> list[dict]:
        return [info.__dict__ for info in (self.calendar.info, self.tasks.info, self.reminders.info)]


_services: Services | None = None


def build_local_services() -> Services:
    return Services(
        calendar=LocalCalendarProvider(),
        tasks=LocalTaskProvider(),
        reminders=LocalReminderProvider(),
        mode="local",
    )


def build_services(mode: str | None = None) -> Services:
    mode = (mode or PROVIDER_MODE).lower()
    if mode == "mcp":
        # Boundary only: real MCP servers are connected during the hackathon.
        from .mcp_adapter import build_mcp_services

        return build_mcp_services()
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
    return [services.calendar.info, services.tasks.info, services.reminders.info]
