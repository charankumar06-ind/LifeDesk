"""Domain models shared by providers, services and the API layer.

These are provider-agnostic: a future MCP provider must return the same shapes,
which is what keeps the workflow engine and UI unchanged when providers swap.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Priority = Literal["low", "medium", "high", "urgent"]
TaskStatus = Literal["todo", "in_progress", "done"]
EventKind = Literal["meeting", "focus", "study", "personal", "break"]
ActionStatus = Literal["proposed", "approved", "rejected", "executing", "executed", "failed"]
WorkflowStatus = Literal["pending_approval", "executing", "completed", "partial", "rejected", "failed"]

PRIORITY_RANK: dict[str, int] = {"urgent": 0, "high": 1, "medium": 2, "low": 3}


class Event(BaseModel):
    id: str
    title: str
    description: str = ""
    start_at: datetime
    end_at: datetime
    location: str = ""
    kind: str = "meeting"
    source: str = "local"
    created_at: datetime
    updated_at: datetime


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    description: str = Field(default="", max_length=2000)
    start_at: datetime
    end_at: datetime
    location: str = Field(default="", max_length=160)
    kind: EventKind = "meeting"

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be empty")
        return value

    @model_validator(mode="after")
    def _check_window(self) -> "EventCreate":
        if self.end_at <= self.start_at:
            raise ValueError("End time must be after start time")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    start_at: datetime | None = None
    end_at: datetime | None = None
    location: str | None = Field(default=None, max_length=160)
    kind: EventKind | None = None

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> "EventUpdate":
        """Every event column is NOT NULL, so explicit nulls are invalid input."""
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"'{field}' cannot be null")
        return self


class Task(BaseModel):
    id: str
    title: str
    description: str = ""
    status: TaskStatus = "todo"
    priority: Priority = "medium"
    due_at: datetime | None = None
    estimate_minutes: int = 60
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    description: str = Field(default="", max_length=2000)
    status: TaskStatus = "todo"
    priority: Priority = "medium"
    due_at: datetime | None = None
    estimate_minutes: int = Field(default=60, ge=15, le=480)
    tags: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be empty")
        return value

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str]) -> list[str]:
        return [tag.strip()[:32] for tag in value if tag and tag.strip()][:12]


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_at: datetime | None = None
    estimate_minutes: int | None = Field(default=None, ge=15, le=480)
    tags: list[str] | None = None

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> "TaskUpdate":
        """An explicit null means "clear this field"; only nullable fields allow it."""
        for field in self.model_fields_set:
            if getattr(self, field) is None and field not in {"due_at", "tags"}:
                raise ValueError(f"'{field}' cannot be null")
        return self


class Reminder(BaseModel):
    id: str
    title: str
    note: str = ""
    remind_at: datetime
    status: Literal["pending", "dismissed"] = "pending"
    created_at: datetime
    updated_at: datetime


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    note: str = Field(default="", max_length=1000)
    remind_at: datetime


class EmailMessage(BaseModel):
    """One outbound email. Recipients are validated before any provider is called."""

    to: list[str] = Field(min_length=1, max_length=10)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)

    @field_validator("to")
    @classmethod
    def _clean_recipients(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            address = item.strip()
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address):
                raise ValueError(f"'{item}' is not a valid email address")
            if address not in cleaned:
                cleaned.append(address)
        if not cleaned:
            raise ValueError("At least one recipient is required")
        return cleaned

    @field_validator("subject", "body")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Subject and body cannot be empty")
        return value


class WorkflowAction(BaseModel):
    id: str
    workflow_id: str
    order_index: int
    action_type: str
    provider: str
    title: str
    description: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    preview: dict[str, Any] = Field(default_factory=dict)
    status: ActionStatus = "proposed"
    result: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    idempotency_key: str
    created_at: datetime
    updated_at: datetime
    executed_at: datetime | None = None


class Workflow(BaseModel):
    id: str
    command: str
    intent: str
    intent_label: str
    summary: str = ""
    plan: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    status: WorkflowStatus = "pending_approval"
    provider_mode: str = "local"
    ai_mode: str = "deterministic"
    target_date: str | None = None
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None = None
    executed_at: datetime | None = None
    error: str | None = None
    actions: list[WorkflowAction] = Field(default_factory=list)


class ActivityEntry(BaseModel):
    id: str
    workflow_id: str | None = None
    action_id: str | None = None
    provider_type: str
    provider_name: str
    operation: str
    status: Literal["success", "failed", "rejected"]
    message: str = ""
    simulated: bool = True
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
