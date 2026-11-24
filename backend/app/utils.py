"""Small date/time + serialisation helpers used across services."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

ISO_FMT = "%Y-%m-%dT%H:%M:%S"


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat(timespec="seconds")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def loads(value: str | None, fallback: Any = None) -> Any:
    if not value:
        return fallback if fallback is not None else {}
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback if fallback is not None else {}


def parse_hhmm(value: str, fallback: time) -> time:
    try:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))
    except (ValueError, AttributeError):
        return fallback


def day_window(day: date, start_hhmm: str, end_hhmm: str) -> tuple[datetime, datetime]:
    start = datetime.combine(day, parse_hhmm(start_hhmm, time(9, 0)))
    end = datetime.combine(day, parse_hhmm(end_hhmm, time(18, 0)))
    if end <= start:
        end = start + timedelta(hours=8)
    return start, end


def as_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return date.today()


def minutes_between(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // 60))


def fmt_time(value: datetime, time_format: str = "24h") -> str:
    """Portable 12h/24h formatting (Windows strftime lacks %-I)."""
    if time_format == "12h":
        hour = value.hour % 12 or 12
        suffix = "AM" if value.hour < 12 else "PM"
        return f"{hour}:{value.minute:02d} {suffix}"
    return f"{value.hour:02d}:{value.minute:02d}"


def spoken_range(start: datetime, end: datetime, time_format: str = "24h") -> str:
    return f"{fmt_time(start, time_format)}–{fmt_time(end, time_format)}"
