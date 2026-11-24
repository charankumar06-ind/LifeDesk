"""SQLite-backed task provider (local simulated tool)."""

from __future__ import annotations

from ..db import get_db
from ..domain import Task, TaskCreate, TaskUpdate
from ..utils import dumps, iso, loads, new_id, now, parse_dt
from .base import ProviderInfo, TaskProvider

COLUMNS = (
    "id, title, description, status, priority, due_at, estimate_minutes, tags,"
    " created_at, updated_at, completed_at"
)


def row_to_task(row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
        due_at=parse_dt(row["due_at"]),
        estimate_minutes=row["estimate_minutes"],
        tags=loads(row["tags"], []),
        created_at=parse_dt(row["created_at"]),
        updated_at=parse_dt(row["updated_at"]),
        completed_at=parse_dt(row["completed_at"]),
    )


class LocalTaskProvider(TaskProvider):
    info = ProviderInfo(
        key="local-tasks",
        label="Local Tasks",
        kind="local",
        transport="SQLite",
        status="connected",
        note="Simulated tool calls backed by the local SQLite database.",
    )

    def list_tasks(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
    ) -> list[Task]:
        clauses: list[str] = []
        params: list[object] = []
        if status == "open":
            clauses.append("status != 'done'")
        elif status:
            clauses.append("status = ?")
            params.append(status)
        if priority:
            clauses.append("priority = ?")
            params.append(priority)
        if search:
            clauses.append("(LOWER(title) LIKE ? OR LOWER(description) LIKE ?)")
            needle = f"%{search.lower()}%"
            params.extend([needle, needle])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with get_db() as conn:
            rows = conn.execute(
                f"SELECT {COLUMNS} FROM tasks {where}"
                " ORDER BY CASE status WHEN 'done' THEN 1 ELSE 0 END,"
                " CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,"
                " COALESCE(due_at, '9999'), created_at",
                params,
            ).fetchall()
        return [row_to_task(row) for row in rows]

    def get_task(self, task_id: str) -> Task | None:
        with get_db() as conn:
            row = conn.execute(f"SELECT {COLUMNS} FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return row_to_task(row) if row else None

    def create_task(self, data: TaskCreate) -> Task:
        task_id = new_id("tsk")
        stamp = iso(now())
        completed_at = stamp if data.status == "done" else None
        with get_db() as conn:
            conn.execute(
                "INSERT INTO tasks (id, title, description, status, priority, due_at, estimate_minutes,"
                " tags, created_at, updated_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task_id,
                    data.title.strip(),
                    data.description.strip(),
                    data.status,
                    data.priority,
                    iso(data.due_at),
                    data.estimate_minutes,
                    dumps(data.tags),
                    stamp,
                    stamp,
                    completed_at,
                ),
            )
        task = self.get_task(task_id)
        assert task is not None
        return task

    def update_task(self, task_id: str, data: TaskUpdate) -> Task:
        fields = data.model_dump(exclude_unset=True)
        existing = self.get_task(task_id)
        if existing is None:
            raise KeyError(task_id)
        if not fields:
            return existing
        assignments: list[str] = []
        values: list[object] = []
        for key, value in fields.items():
            if key == "due_at":
                value = iso(value)
            elif key == "tags":
                value = dumps(value or [])
            assignments.append(f"{key} = ?")
            values.append(value)
        if "status" in fields:
            if fields["status"] == "done":
                assignments.append("completed_at = ?")
                values.append(iso(now()) if existing.completed_at is None else iso(existing.completed_at))
            else:
                assignments.append("completed_at = NULL")
        assignments.append("updated_at = ?")
        values.append(iso(now()))
        values.append(task_id)
        with get_db() as conn:
            conn.execute(f"UPDATE tasks SET {', '.join(assignments)} WHERE id = ?", values)
        task = self.get_task(task_id)
        assert task is not None
        return task

    def delete_task(self, task_id: str) -> None:
        with get_db() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            if cursor.rowcount == 0:
                raise KeyError(task_id)


def seed_task(conn, *, title: str, priority: str, due_at=None, estimate_minutes: int = 60,
              status: str = "todo", tags: list[str] | None = None, description: str = "",
              completed_at=None) -> str:
    task_id = new_id("tsk")
    stamp = iso(now())
    conn.execute(
        "INSERT INTO tasks (id, title, description, status, priority, due_at, estimate_minutes, tags,"
        " created_at, updated_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            task_id,
            title,
            description,
            status,
            priority,
            iso(due_at),
            estimate_minutes,
            dumps(tags or []),
            stamp,
            stamp,
            iso(completed_at),
        ),
    )
    return task_id
