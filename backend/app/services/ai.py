"""AI provider abstraction.

The prototype runs the deterministic interpreter. It is *not* an LLM and the UI
says so explicitly. `LLMProvider` is the extension point for the hackathon:
implement `interpret()` with a hosted or local model and set
LIFEDESK_AI_PROVIDER=llm; no route or workflow code has to change.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .intent import IntentResult, parse_command


@dataclass(frozen=True)
class AIProviderInfo:
    key: str
    label: str
    mode: str
    description: str
    llm_configured: bool
    requires_api_key: bool = False


class AIProvider(ABC):
    info: AIProviderInfo

    @abstractmethod
    def interpret(self, command: str, context: dict[str, Any] | None = None) -> IntentResult: ...


class DeterministicAIProvider(AIProvider):
    """Rule-based intent parsing — reliable on stage, no network, no API key."""

    info = AIProviderInfo(
        key="deterministic",
        label="Deterministic intent interpreter",
        mode="deterministic",
        description=(
            "Keyword + pattern rules over the local workspace. Runs offline, never calls a model, "
            "and never invents actions outside the supported intents."
        ),
        llm_configured=False,
        requires_api_key=False,
    )

    def interpret(self, command: str, context: dict[str, Any] | None = None) -> IntentResult:
        return parse_command(command)


class LLMProvider(AIProvider):
    """Future hackathon extension — not enabled in this prototype."""

    info = AIProviderInfo(
        key="llm",
        label="LLM planner (not configured)",
        mode="llm",
        description="Optional model-backed interpreter. Disabled in this build.",
        llm_configured=False,
        requires_api_key=True,
    )

    def interpret(self, command: str, context: dict[str, Any] | None = None) -> IntentResult:
        raise RuntimeError("LLM provider is not configured in this build.")


_deterministic = DeterministicAIProvider()


def get_ai_provider() -> AIProvider:
    requested = os.environ.get("LIFEDESK_AI_PROVIDER", "deterministic").lower()
    if requested == "llm":
        # No key/model is configured in the demo build: fall back, and say so.
        return _deterministic
    return _deterministic


def ai_status() -> dict[str, Any]:
    provider = get_ai_provider()
    return {
        "mode": provider.info.mode,
        "label": provider.info.label,
        "description": provider.info.description,
        "llm_configured": provider.info.llm_configured,
        "requires_api_key": provider.info.requires_api_key,
        "requested": os.environ.get("LIFEDESK_AI_PROVIDER", "deterministic"),
        "fallback_active": os.environ.get("LIFEDESK_AI_PROVIDER", "deterministic").lower() != provider.info.mode,
        "supported_intents": [
            {"intent": "plan_day", "example": "Plan my day"},
            {"intent": "list_pending", "example": "Show pending tasks"},
            {"intent": "schedule_study", "example": "Schedule a two-hour Python study session"},
            {"intent": "create_reminder", "example": "Remind me to submit the form at 17:00"},
            {"intent": "schedule_event", "example": "Schedule a meeting with Sam tomorrow at 10:00"},
            {"intent": "create_task", "example": "Create a task to review lecture notes tomorrow"},
            {"intent": "send_email", "example": "Send mail to friend@example.com saying HI"},
            {"intent": "daily_briefing", "example": "Give me my daily briefing"},
            {"intent": "weekly_review", "example": "Review my week"},
            {"intent": "find_free_time", "example": "Find a free 90-minute slot tomorrow"},
            {"intent": "complete_task", "example": "Complete task review lecture notes"},
            {"intent": "dismiss_reminder", "example": "Dismiss the reminder about course form"},
        ],
    }
