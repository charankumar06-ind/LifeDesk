"""Settings persistence + validation."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..db import get_db

HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

DEFAULT_SETTINGS: dict[str, object] = {
    "display_name": "Ari Mensah",
    "role": "Computer science student",
    "workspace": "Personal desk",
    "time_format": "24h",
    "week_start": "monday",
    "day_start": "08:30",
    "day_end": "19:00",
    "focus_block_minutes": 90,
    "default_study_minutes": 120,
    "buffer_minutes": 10,
    "min_block_minutes": 30,
}


class SettingsUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)
    role: str = Field(default="", max_length=80)
    workspace: str = Field(default="", max_length=80)
    time_format: Literal["12h", "24h"] = "24h"
    week_start: Literal["monday", "sunday"] = "monday"
    day_start: str = "08:30"
    day_end: str = "19:00"
    focus_block_minutes: int = Field(default=90, ge=15, le=480)
    default_study_minutes: int = Field(default=120, ge=15, le=480)
    buffer_minutes: int = Field(default=10, ge=0, le=60)
    min_block_minutes: int = Field(default=30, ge=15, le=120)

    @field_validator("day_start", "day_end")
    @classmethod
    def _time_format(cls, value: str) -> str:
        value = value.strip()
        if not HHMM.match(value):
            raise ValueError("Use 24-hour HH:MM format, e.g. 09:00")
        return value

    @field_validator("display_name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name cannot be empty")
        return value


def _coerce(defaults: dict[str, object], values: dict[str, str]) -> dict[str, object]:
    merged = dict(defaults)
    for key, raw in values.items():
        if key not in defaults:
            continue
        default = defaults[key]
        if isinstance(default, int):
            try:
                merged[key] = int(raw)
            except ValueError:
                merged[key] = default
        else:
            merged[key] = raw
    return merged


def get_settings() -> dict[str, object]:
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    values = {row["key"]: row["value"] for row in rows}
    return _coerce(DEFAULT_SETTINGS, values)


def update_settings(payload: SettingsUpdate) -> dict[str, object]:
    data = payload.model_dump()
    with get_db() as conn:
        for key, value in data.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
    return get_settings()
