"""Provider interfaces.

The workflow engine only talks to these abstract interfaces. Swapping
`LocalCalendarProvider` for `McpCalendarProvider` is therefore a composition
change in `providers/registry.py`, not a redesign.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from ..domain import Event, EventCreate, EventUpdate, Reminder, ReminderCreate, Task, TaskCreate, TaskUpdate


class ProviderError(RuntimeError):
    """Raised when a provider cannot complete an operation."""


class ProviderNotConfigured(ProviderError):
    """Raised by provider stubs that require external configuration/credentials."""


@dataclass(frozen=True)
class ProviderInfo:
    key: str
    label: str
    kind: Literal["local", "mcp"]
    transport: str
    status: Literal["connected", "not_configured", "error"]
    note: str


class CalendarProvider(ABC):
    """Calendar CRUD boundary. Implementations must return timezone-naive local datetimes."""

    info: ProviderInfo

    @abstractmethod
    def list_events(self, start: datetime, end: datetime) -> list[Event]: ...

    @abstractmethod
    def get_event(self, event_id: str) -> Event | None: ...

    @abstractmethod
    def create_event(self, data: EventCreate, source: str = "local") -> Event: ...

    @abstractmethod
    def update_event(self, event_id: str, data: EventUpdate) -> Event: ...

    @abstractmethod
    def delete_event(self, event_id: str) -> None: ...


class TaskProvider(ABC):
    """Task CRUD/filtering boundary."""

    info: ProviderInfo

    @abstractmethod
    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
    ) -> list[Task]: ...

    @abstractmethod
    def get_task(self, task_id: str) -> Task | None: ...

    @abstractmethod
    def create_task(self, data: TaskCreate) -> Task: ...

    @abstractmethod
    def update_task(self, task_id: str, data: TaskUpdate) -> Task: ...

    @abstractmethod
    def delete_task(self, task_id: str) -> None: ...


class ReminderProvider(ABC):
    """Reminder boundary (kept separate so it can later be a notification MCP tool)."""

    info: ProviderInfo

    @abstractmethod
    def list_reminders(self, *, status: str | None = None) -> list[Reminder]: ...

    @abstractmethod
    def create_reminder(self, data: ReminderCreate) -> Reminder: ...

    @abstractmethod
    def dismiss_reminder(self, reminder_id: str) -> Reminder: ...
