"""SQLite-backed reminder provider."""

from __future__ import annotations

from ..db import get_db
from ..domain import Reminder, ReminderCreate
from ..utils import iso, new_id, now, parse_dt
from .base import ProviderInfo, ReminderProvider


def row_to_reminder(row) -> Reminder:
    return Reminder(
        id=row["id"],
        title=row["title"],
        note=row["note"],
        remind_at=parse_dt(row["remind_at"]),
        status=row["status"],
        created_at=parse_dt(row["created_at"]),
        updated_at=parse_dt(row["updated_at"]),
    )


class LocalReminderProvider(ReminderProvider):
    info = ProviderInfo(
        key="local-reminders",
        label="Local Reminders",
        kind="local",
        transport="SQLite",
        status="connected",
        note="Simulated notification tool backed by local data.",
    )

    def list_reminders(self, *, status: str | None = None) -> list[Reminder]:
        query = "SELECT * FROM reminders"
        params: list[object] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY remind_at"
        with get_db() as conn:
            rows = conn.execute(query, params).fetchall()
        return [row_to_reminder(row) for row in rows]

    def create_reminder(self, data: ReminderCreate) -> Reminder:
        reminder_id = new_id("rem")
        stamp = iso(now())
        with get_db() as conn:
            conn.execute(
                "INSERT INTO reminders (id, title, note, remind_at, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'pending', ?, ?)",
                (reminder_id, data.title.strip(), data.note.strip(), iso(data.remind_at), stamp, stamp),
            )
            row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        return row_to_reminder(row)

    def dismiss_reminder(self, reminder_id: str) -> Reminder:
        with get_db() as conn:
            cursor = conn.execute(
                "UPDATE reminders SET status = 'dismissed', updated_at = ? WHERE id = ?",
                (iso(now()), reminder_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(reminder_id)
            row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        return row_to_reminder(row)
