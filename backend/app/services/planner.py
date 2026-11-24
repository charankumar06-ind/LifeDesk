"""Conflict-aware daily planning engine.

Pure functions over domain models: no database or provider access, so it works
identically against local or future MCP data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from ..domain import PRIORITY_RANK, Event, Task
from ..utils import day_window, fmt_time, iso, minutes_between


@dataclass
class StudyRequest:
    topic: str
    minutes: int


@dataclass
class ScheduleBlock:
    start: datetime
    end: datetime
    title: str
    block_type: str  # event | task | study
    kind: str
    reason: str
    task_id: str | None = None
    event_id: str | None = None
    priority: str | None = None


@dataclass
class PlanConflict:
    severity: str  # info | warning | critical
    title: str
    detail: str
    related_ids: list[str] = field(default_factory=list)


@dataclass
class DayPlan:
    day: date
    window_start: datetime
    window_end: datetime
    blocks: list[ScheduleBlock]
    conflicts: list[PlanConflict]
    rationale: list[str]
    unscheduled_tasks: list[Task]
    stats: dict[str, int]
    gaps: list[tuple[datetime, datetime]]

    def as_dict(self, time_format: str = "24h") -> dict:
        return {
            "date": self.day.isoformat(),
            "window": {
                "start_at": iso(self.window_start),
                "end_at": iso(self.window_end),
                "label": f"{fmt_time(self.window_start, time_format)}–{fmt_time(self.window_end, time_format)}",
            },
            "blocks": [
                {
                    "start_at": iso(block.start),
                    "end_at": iso(block.end),
                    "display": f"{fmt_time(block.start, time_format)}–{fmt_time(block.end, time_format)}",
                    "title": block.title,
                    "type": block.block_type,
                    "kind": block.kind,
                    "reason": block.reason,
                    "task_id": block.task_id,
                    "event_id": block.event_id,
                    "priority": block.priority,
                    "duration_minutes": minutes_between(block.start, block.end),
                }
                for block in sorted(self.blocks, key=lambda item: item.start)
            ],
            "conflicts": [
                {"severity": c.severity, "title": c.title, "detail": c.detail, "related_ids": c.related_ids}
                for c in self.conflicts
            ],
            "rationale": self.rationale,
            "unscheduled_tasks": [
                {"id": task.id, "title": task.title, "priority": task.priority, "estimate_minutes": task.estimate_minutes}
                for task in self.unscheduled_tasks
            ],
            "stats": self.stats,
            "gaps": [
                {
                    "start_at": iso(start),
                    "end_at": iso(end),
                    "display": f"{fmt_time(start, time_format)}–{fmt_time(end, time_format)}",
                    "duration_minutes": minutes_between(start, end),
                }
                for start, end in self.gaps
            ],
        }


def _merge_busy(events: list[Event]) -> list[tuple[datetime, datetime]]:
    intervals = sorted(((event.start_at, event.end_at) for event in events), key=lambda item: item[0])
    merged: list[tuple[datetime, datetime]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _free_gaps(window_start: datetime, window_end: datetime, busy: list[tuple[datetime, datetime]]) -> list[list[datetime]]:
    gaps: list[list[datetime]] = []
    cursor = window_start
    for start, end in busy:
        if start > cursor:
            gaps.append([cursor, min(start, window_end)])
        cursor = max(cursor, end)
        if cursor >= window_end:
            break
    if cursor < window_end:
        gaps.append([cursor, window_end])
    return [gap for gap in gaps if gap[1] > gap[0]]


def _rank_tasks(tasks: list[Task], day: date) -> list[Task]:
    def key(task: Task):
        due = task.due_at.date() if task.due_at else date.max
        urgency = 0 if due <= day else 1
        return (urgency, PRIORITY_RANK.get(task.priority, 9), due, -(task.estimate_minutes or 0))

    return sorted([task for task in tasks if task.status != "done"], key=key)


def build_day_plan(
    *,
    day: date,
    events: list[Event],
    tasks: list[Task],
    settings: dict,
    study: StudyRequest | None = None,
    unrelated_pending: list[Task] | None = None,
) -> DayPlan:
    time_format = str(settings.get("time_format", "24h"))
    window_start, window_end = day_window(day, str(settings.get("day_start", "08:30")), str(settings.get("day_end", "19:00")))
    min_block = int(settings.get("min_block_minutes", 30))
    buffer_minutes = int(settings.get("buffer_minutes", 10))

    day_events = sorted(
        [event for event in events if event.end_at > window_start and event.start_at < window_end],
        key=lambda event: event.start_at,
    )
    busy = _merge_busy(day_events)
    gaps = _free_gaps(window_start, window_end, busy)

    conflicts: list[PlanConflict] = []
    rationale: list[str] = []

    # Overlapping events already on the calendar.
    for index, first in enumerate(day_events):
        for second in day_events[index + 1 :]:
            if second.start_at < first.end_at:
                conflicts.append(
                    PlanConflict(
                        severity="warning",
                        title="Calendar overlap",
                        detail=(
                            f"'{first.title}' ({fmt_time(first.start_at, time_format)}–{fmt_time(first.end_at, time_format)}) "
                            f"overlaps '{second.title}' ({fmt_time(second.start_at, time_format)}–{fmt_time(second.end_at, time_format)})."
                        ),
                        related_ids=[first.id, second.id],
                    )
                )

    blocks: list[ScheduleBlock] = [
        ScheduleBlock(
            start=event.start_at,
            end=event.end_at,
            title=event.title,
            block_type="event",
            kind=event.kind,
            reason="Already on the calendar.",
            event_id=event.id,
        )
        for event in day_events
    ]

    def allocate(minutes: int, *, preferred: datetime | None = None) -> tuple[datetime, datetime] | None:
        best_index = None
        for index, (gap_start, gap_end) in enumerate(gaps):
            if minutes_between(gap_start, gap_end) >= minutes:
                if preferred is not None and gap_start <= preferred < gap_end:
                    best_index = index
                    break
                if best_index is None:
                    best_index = index
        if best_index is None:
            return None
        gap_start, gap_end = gaps[best_index]
        start = gap_start
        end = start + timedelta(minutes=minutes)
        next_start = end + timedelta(minutes=buffer_minutes)
        if minutes_between(next_start, gap_end) >= min_block:
            gaps[best_index] = [next_start, gap_end]
        else:
            gaps.pop(best_index)
        return start, end

    # 1. Protect the explicitly requested study session before anything else.
    if study and study.minutes > 0:
        preferred = datetime.combine(day, datetime.min.time()).replace(hour=14)
        slot = allocate(study.minutes, preferred=preferred)
        if slot:
            start, end = slot
            blocks.append(
                ScheduleBlock(
                    start=start,
                    end=end,
                    title=f"{study.topic} study session" if study.topic != "Focus" else "Study session",
                    block_type="study",
                    kind="study",
                    priority="high",
                    reason=(
                        f"Requested session ({study.minutes} min) is reserved before optional work, in the "
                        f"first conflict-free slot large enough for deep work."
                    ),
                )
            )
            rationale.append(
                f"Reserved {study.minutes} minutes for {study.topic} at {fmt_time(start, time_format)}–"
                f"{fmt_time(end, time_format)} — the request was explicit, so it outranks flexible tasks."
            )
        else:
            conflicts.append(
                PlanConflict(
                    severity="critical",
                    title="Study session cannot fit",
                    detail=(
                        f"No free {study.minutes}-minute gap remains between "
                        f"{fmt_time(window_start, time_format)} and {fmt_time(window_end, time_format)}."
                    ),
                )
            )
            rationale.append("The requested study session was not scheduled because no gap was long enough.")

    # 2. Rank remaining pending tasks by deadline proximity, then priority.
    # Skip tasks that already have a focus block on the calendar for this day so
    # re-planning does not propose duplicate events.
    existing_titles = {event.title.strip().lower() for event in day_events}
    ranked_all = _rank_tasks(tasks, day)
    already_planned = [
        task for task in ranked_all if f"focus: {task.title}".strip().lower() in existing_titles
    ]
    ranked = [task for task in ranked_all if task not in already_planned]
    if already_planned:
        rationale.append(
            "Already scheduled today (existing focus block): "
            + ", ".join(task.title for task in already_planned)
            + ". Those tasks were skipped to avoid duplicate blocks."
        )

    unscheduled: list[Task] = []
    for task in ranked:
        estimate = max(min_block, min(task.estimate_minutes or int(settings.get("focus_block_minutes", 90)), 180))
        slot = allocate(estimate)
        if not slot:
            unscheduled.append(task)
            continue
        start, end = slot
        overdue = task.due_at is not None and task.due_at < datetime.combine(day, datetime.min.time())
        reason = f"{task.priority.capitalize()} priority"
        if task.due_at:
            reason += f", due {fmt_time(task.due_at, time_format)} on {task.due_at.strftime('%d %b')}"
        if overdue:
            reason += " (past deadline)"
        blocks.append(
            ScheduleBlock(
                start=start,
                end=end,
                title=f"Focus: {task.title}",
                block_type="task",
                kind="focus",
                priority=task.priority,
                task_id=task.id,
                reason=f"{reason}. Scheduled in the first gap that fits {estimate} minutes.",
            )
        )
        rationale.append(
            f"{task.priority.capitalize()} priority '{task.title}' placed at {fmt_time(start, time_format)}."
        )

    if unscheduled:
        rationale.append(
            "Not scheduled today (no gap long enough): " + ", ".join(task.title for task in unscheduled) + "."
        )

    # 3. Deadline and capacity checks.
    due_today = [
        task
        for task in ranked
        if task.due_at is not None and task.due_at.date() <= day and task not in unscheduled
    ]
    for task in due_today:
        if task.due_at and task.due_at.date() < day:
            conflicts.append(
                PlanConflict(
                    severity="critical",
                    title="Overdue task",
                    detail=f"'{task.title}' was due {task.due_at.strftime('%d %b %H:%M')} and is still open.",
                    related_ids=[task.id],
                )
            )
        else:
            conflicts.append(
                PlanConflict(
                    severity="info",
                    title="Due today",
                    detail=f"'{task.title}' is due today at {fmt_time(task.due_at, time_format)}.",
                    related_ids=[task.id],
                )
            )

    remaining_tasks = related = None
    if unrelated_pending:
        remaining_tasks = [task for task in unrelated_pending if task.status != "done"]
    scheduled_task_minutes = sum(
        minutes_between(block.start, block.end) for block in blocks if block.block_type in {"task", "study"}
    )
    busy_minutes = sum(minutes_between(block.start, block.end) for block in blocks if block.block_type == "event")
    free_minutes = sum(minutes_between(start, end) for start, end in gaps)
    total_pending = len(ranked) + len(already_planned) + (len(remaining_tasks) if remaining_tasks else 0)

    if not day_events:
        conflicts.append(
            PlanConflict(
                severity="info",
                title="Open calendar",
                detail="No events are booked today, so the whole working window is available.",
            )
        )

    if not rationale:
        rationale.append("No pending tasks were available to schedule; the calendar was left untouched.")
    rationale.append(
        f"Working window {fmt_time(window_start, time_format)}–{fmt_time(window_end, time_format)} with "
        f"{buffer_minutes}-minute buffers between proposed blocks."
    )

    stats = {
        "busy_minutes": busy_minutes,
        "scheduled_focus_minutes": scheduled_task_minutes,
        "free_minutes": max(0, free_minutes),
        "tasks_considered": total_pending,
        "tasks_scheduled": sum(1 for block in blocks if block.block_type == "task"),
        "tasks_unscheduled": len(unscheduled) + (len(remaining_tasks) if remaining_tasks else 0),
        "events": len(day_events),
    }

    return DayPlan(
        day=day,
        window_start=window_start,
        window_end=window_end,
        blocks=blocks,
        conflicts=conflicts,
        rationale=rationale,
        unscheduled_tasks=unscheduled,
        stats=stats,
        gaps=[tuple(gap) for gap in gaps],
    )
