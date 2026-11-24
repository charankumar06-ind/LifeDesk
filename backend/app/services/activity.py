"""Activity monitor persistence: one row per executed/attempted tool call."""

from __future__ import annotations

from typing import Any

from ..db import get_db
from ..domain import ActivityEntry
from ..utils import dumps, iso, loads, new_id, now, parse_dt


def row_to_activity(row) -> ActivityEntry:
    return ActivityEntry(
        id=row["id"],
        workflow_id=row["workflow_id"],
        action_id=row["action_id"],
        provider_type=row["provider_type"],
        provider_name=row["provider_name"],
        operation=row["operation"],
        status=row["status"],
        message=row["message"],
        simulated=bool(row["simulated"]),
        detail=loads(row["detail"], {}),
        created_at=parse_dt(row["created_at"]),
    )


def log_activity(
    *,
    provider_type: str,
    provider_name: str,
    operation: str,
    status: str,
    message: str = "",
    workflow_id: str | None = None,
    action_id: str | None = None,
    detail: dict[str, Any] | None = None,
    simulated: bool = True,
) -> ActivityEntry:
    entry_id = new_id("act")
    stamp = iso(now())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO activity (id, workflow_id, action_id, provider_type, provider_name, operation,"
            " status, message, simulated, detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry_id,
                workflow_id,
                action_id,
                provider_type,
                provider_name,
                operation,
                status,
                message,
                1 if simulated else 0,
                dumps(detail or {}),
                stamp,
            ),
        )
        row = conn.execute("SELECT * FROM activity WHERE id = ?", (entry_id,)).fetchone()
    return row_to_activity(row)


def list_activity(
    *,
    limit: int = 100,
    status: str | None = None,
    provider_type: str | None = None,
) -> list[ActivityEntry]:
    clauses: list[str] = []
    params: list[object] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if provider_type:
        clauses.append("provider_type = ?")
        params.append(provider_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(limit, 500)))
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM activity {where} ORDER BY created_at DESC, rowid DESC LIMIT ?", params
        ).fetchall()
    return [row_to_activity(row) for row in rows]


def activity_summary() -> dict[str, Any]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS count FROM activity GROUP BY status"
        ).fetchall()
        providers = conn.execute(
            "SELECT provider_type, COUNT(*) AS count FROM activity GROUP BY provider_type ORDER BY count DESC"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS count FROM activity").fetchone()["count"]
    counts = {"success": 0, "failed": 0, "rejected": 0}
    for row in rows:
        counts[row["status"]] = row["count"]
    return {
        "total": total,
        "counts": counts,
        "providers": [{"provider_type": r["provider_type"], "count": r["count"]} for r in providers],
    }
