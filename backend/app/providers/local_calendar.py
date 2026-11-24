"""SQLite-backed calendar provider (local simulated tool)."""

from __future__ import annotations

from datetime import datetime

from ..db import get_db
from ..domain import Event, EventCreate, EventUpdate
from ..utils import iso, loads, new_id, now, parse_dt
from .base import CalendarProvider, ProviderInfo

DEFAULT_COLUMNS = "id, title, description, start_at, end_at, location, kind, source, created_at, updated_at"


def row_to_event(row) -> Event:
    return Event(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        start_at=parse_dt(row["start_at"]),
        end_at=parse_dt(row["end_at"]),
        location=row["location"],
        kind=row["kind"],
        source=row["source"],
        created_at=parse_dt(row["created_at"]),
        updated_at=parse_dt(row["updated_at"]),
    )


class LocalCalendarProvider(CalendarProvider):
    info = ProviderInfo(
        key="local-calendar",
        label="Local Calendar",
        kind="local",
        transport="SQLite",
        status="connected",
        note="Simulated tool calls backed by the local SQLite database.",
    )

    def list_events(self, start: datetime, end: datetime) -> list[Event]:
        with get_db() as conn:
            rows = conn.execute(
                f"SELECT {DEFAULT_COLUMNS} FROM events WHERE start_at < ? AND end_at > ? ORDER BY start_at",
                (iso(end), iso(start)),
            ).fetchall()
        return [row_to_event(row) for row in rows]

    def get_event(self, event_id: str) -> Event | None:
        with get_db() as conn:
            row = conn.execute(
                f"SELECT {DEFAULT_COLUMNS} FROM events WHERE id = ?", (event_id,)
            ).fetchone()
        return row_to_event(row) if row else None

    def create_event(self, data: EventCreate, source: str = "local") -> Event:
        event_id = new_id("evt")
        stamp = iso(now())
        with get_db() as conn:
            conn.execute(
                "INSERT INTO events (id, title, description, start_at, end_at, location, kind, source, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    data.title.strip(),
                    data.description.strip(),
                    iso(data.start_at),
                    iso(data.end_at),
                    data.location.strip(),
                    data.kind,
                    source,
                    stamp,
                    stamp,
                ),
            )
        event = self.get_event(event_id)
        assert event is not None
        return event

    def update_event(self, event_id: str, data: EventUpdate) -> Event:
        fields = data.model_dump(exclude_unset=True)
        if not fields:
            existing = self.get_event(event_id)
            if existing is None:
                raise KeyError(event_id)
            return existing
        assignments = []
        values = []
        for key, value in fields.items():
            if key in {"start_at", "end_at"}:
                value = iso(value)
            assignments.append(f"{key} = ?")
            values.append(value)
        assignments.append("updated_at = ?")
        values.append(iso(now()))
        values.append(event_id)
        with get_db() as conn:
            cursor = conn.execute(f"UPDATE events SET {', '.join(assignments)} WHERE id = ?", values)
            if cursor.rowcount == 0:
                raise KeyError(event_id)
        event = self.get_event(event_id)
        assert event is not None
        return event

    def delete_event(self, event_id: str) -> None:
        with get_db() as conn:
            cursor = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
            if cursor.rowcount == 0:
                raise KeyError(event_id)


def seed_event(conn, *, title: str, start: datetime, end: datetime, kind: str = "meeting",
               location: str = "", description: str = "", source: str = "seed") -> str:
    event_id = new_id("evt")
    stamp = iso(now())
    conn.execute(
        "INSERT INTO events (id, title, description, start_at, end_at, location, kind, source, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (event_id, title, description, iso(start), iso(end), location, kind, source, stamp, stamp),
    )
    return event_id


__all__ = ["LocalCalendarProvider", "row_to_event", "seed_event", "loads"]
