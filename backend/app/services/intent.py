"""Deterministic natural-language interpretation.

No model is called. Patterns are intentionally explicit so live demos are
predictable and unsupported requests fail visibly instead of hallucinating.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

KNOWN_TOPICS = [
    "python", "react", "typescript", "javascript", "sql", "algorithms",
    "machine learning", "statistics", "calculus", "linear algebra", "spanish",
    "biology", "chemistry", "history", "economics", "design", "writing",
]

INTENT_LABELS = {
    "plan_day": "Plan my day",
    "list_pending": "Show pending tasks",
    "schedule_study": "Schedule a study session",
    "create_reminder": "Create a reminder",
    "schedule_event": "Schedule a meeting",
    "create_task": "Create a task",
    "complete_task": "Complete a task",
    "dismiss_reminder": "Dismiss a reminder",
    "daily_briefing": "Daily briefing",
    "weekly_review": "Weekly review",
    "find_free_time": "Find free time",
    "send_email": "Send an email",
    "unsupported": "Unsupported request",
}


@dataclass
class IntentResult:
    intent: str
    label: str
    supported: bool
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    matched_rule: str = ""
    warnings: list[str] = field(default_factory=list)


EMAIL_ADDRESS = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _normalise(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip().lower())


def extract_duration_minutes(text: str) -> int | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*[- ]?\s*(hours?|hrs?|h)\b", text)
    if match:
        return int(float(match.group(1).replace(",", ".")) * 60)
    word = re.search(r"(one|two|three|four|five|six|seven|eight|nine|ten)\s*[- ]?\s*(?:hours?|hrs?)", text)
    if word:
        return NUMBER_WORDS[word.group(1)] * 60
    minutes = re.search(r"(\d+)\s*[- ]?\s*(?:minutes?|mins?)\b", text)
    if minutes:
        return int(minutes.group(1))
    return None


def extract_study_topic(text: str) -> str | None:
    for topic in KNOWN_TOPICS:
        if re.search(rf"\b{re.escape(topic)}\b", text):
            return topic.title() if topic not in {"sql"} else "SQL"
    patterns = [
        r"study\s+session\s+(?:on|for|in)\s+([a-z][\w+#. ]{1,30})",
        r"study\s+(?:on|for)\s+([a-z][\w+#. ]{1,30})",
        r"([a-z][\w+#.]{1,20})\s+study\s+session",
        r"study\s+session\s+([a-z][\w+#.]{1,20})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1).strip(" .,")
            if candidate not in {"a", "the", "my", "today", "tomorrow"}:
                return candidate.title()
    return None


def extract_target_date(text: str) -> date:
    today = date.today()
    if re.search(r"\btomorrow\b", text):
        return today + timedelta(days=1)
    if re.search(r"\btoday\b|\bthis afternoon\b|\btonight\b", text):
        return today
    weekday = re.search(r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text)
    if weekday:
        target = WEEKDAYS.index(weekday.group(1))
        ahead = (target - today.weekday()) % 7 or 7
        return today + timedelta(days=ahead)
    bare_weekday = re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text)
    if bare_weekday:
        target = WEEKDAYS.index(bare_weekday.group(1))
        ahead = (target - today.weekday()) % 7 or 7
        return today + timedelta(days=ahead)
    return today


def extract_clock_time(text: str) -> time | None:
    if re.search(r"\bnoon\b", text):
        return time(12, 0)
    match = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text)
    if not match:
        match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None


def extract_relative_minutes(text: str) -> int | None:
    match = re.search(r"\bin\s+(\d+)\s*(minutes?|mins?|hours?|hrs?)\b", text)
    if not match:
        return None
    value = int(match.group(1))
    return value * 60 if match.group(2).startswith("h") else value


def _clean_title(raw: str) -> str:
    value = re.sub(r"\b(today|tomorrow|tonight|please)\b", "", raw, flags=re.IGNORECASE)
    value = re.sub(r"\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip(" .,-")
    return value[:120].strip().capitalize() if value else ""


def parse_command(command: str) -> IntentResult:
    text = _normalise(command)
    if not text:
        return IntentResult(
            intent="unsupported",
            label=INTENT_LABELS["unsupported"],
            supported=False,
            confidence=0.0,
            explanation="The command was empty.",
            matched_rule="empty",
        )

    duration = extract_duration_minutes(text)
    target_date = extract_target_date(text)

    # --- plan my day -------------------------------------------------------
    if re.search(r"\bplan\s+(?:out\s+)?(?:my|the|our)?\s*day\b", text) or text in {"plan my day", "plan day"}:
        entities: dict[str, Any] = {"date": target_date.isoformat()}
        if duration:
            entities["study_minutes"] = duration
        topic = extract_study_topic(text)
        if topic:
            entities["study_topic"] = topic
        assignment_count = re.search(r"\b(one|two|three|four|five|\d+)\s+pending\s+(?:assignments?|tasks?)\b", text)
        if assignment_count:
            raw = assignment_count.group(1)
            entities["pending_hint"] = int(raw) if raw.isdigit() else NUMBER_WORDS.get(raw, 0)
        return IntentResult(
            intent="plan_day",
            label=INTENT_LABELS["plan_day"],
            supported=True,
            confidence=0.96,
            entities=entities,
            explanation=(
                "Matched the day-planning rule. LifeDesk will read local tasks and calendar events, "
                "rank them by priority and deadline, then propose calendar blocks for approval."
            ),
            matched_rule="plan_day / 'plan my day'",
        )

    # --- daily briefing ----------------------------------------------------
    if (
        re.search(r"\b(daily|morning|today'?s)\s+(briefing|brief|summary|agenda)\b", text)
        or re.search(r"\bbrief\s+me\b", text)
        or re.search(r"what(?:'s| is)\s+(?:on|happening)\s+(?:today|my plate)\b", text)
        or re.search(r"\bwhat\s+do\s+i\s+have\s+(?:today|on)\b", text)
        or re.search(r"\bmy\s+day\s+at\s+a\s+glance\b", text)
    ):
        return IntentResult(
            intent="daily_briefing",
            label=INTENT_LABELS["daily_briefing"],
            supported=True,
            confidence=0.95,
            entities={"date": target_date.isoformat()},
            explanation=(
                "Matched the daily-briefing rule. LifeDesk will read today's calendar, open tasks "
                "and pending reminders, then return a read-only summary. Nothing is written."
            ),
            matched_rule="daily_briefing / 'brief me'",
        )

    # --- weekly review -----------------------------------------------------
    if (
        re.search(r"\bweekly\s+(review|summary|recap|report)\b", text)
        or re.search(r"\breview\s+(?:my|the|this)\s+week\b", text)
        or "week in review" in text
        or re.search(r"\bhow\s+(?:was|did)\s+(?:my|the)\s+week\b", text)
    ):
        return IntentResult(
            intent="weekly_review",
            label=INTENT_LABELS["weekly_review"],
            supported=True,
            confidence=0.94,
            entities={},
            explanation=(
                "Matched the weekly-review rule. LifeDesk will read the last seven days of calendar "
                "events, task completions and pending work, then return a read-only recap."
            ),
            matched_rule="weekly_review / 'weekly review'",
        )

    # --- find free time ----------------------------------------------------
    if (
        re.search(r"\b(find|show|get|when)\b.*\b(free|available|open)\b.*\b(time|slot|gap|window)\b", text)
        or re.search(r"\b(free\s+(time|slot|gap|window)|available\s+slot|open\s+slot)\b", text)
        or re.search(r"\bwhen\s+am\s+i\s+free\b", text)
        or re.search(r"\bfind\s+(?:me\s+)?(?:a\s+)?(?:\d+[ -]?(?:minutes?|mins?|hours?|hrs?)\s+)?(?:slot|gap)\b", text)
    ):
        return IntentResult(
            intent="find_free_time",
            label=INTENT_LABELS["find_free_time"],
            supported=True,
            confidence=0.92,
            entities={
                "date": target_date.isoformat(),
                "minutes": max(15, duration or 60),
            },
            explanation=(
                "Matched the free-time rule. LifeDesk will read the calendar for the requested day "
                "and report conflict-free gaps inside your working window. Nothing is written."
            ),
            matched_rule="find_free_time / 'find free time'",
        )

    # --- dismiss reminder (before reminder creation) -----------------------
    if re.search(r"\b(dismiss|clear|close|cancel)\b.{0,25}\breminder\b", text) or (
        "reminder" in text and re.search(r"\b(dismiss|clear|close|cancel)\b", text)
    ):
        raw = re.search(
            r"\b(?:dismiss|clear|close|cancel)\s+(?:the\s+|my\s+|a\s+)?reminder"
            r"(?:\s+(?:about|for|to|on))?\s*(.*)$",
            text,
        )
        query = _clean_title(raw.group(1)) if raw and raw.group(1) else ""
        return IntentResult(
            intent="dismiss_reminder",
            label=INTENT_LABELS["dismiss_reminder"],
            supported=True,
            confidence=0.9,
            entities={"title": query},
            explanation=(
                "Matched the reminder-dismissal rule. LifeDesk will find the matching pending "
                "reminder and propose dismissing it for approval."
            ),
            matched_rule="dismiss_reminder / 'dismiss reminder'",
        )

    # --- complete task -----------------------------------------------------
    complete_match = re.search(
        r"\b(?:complete|finish|close|mark)\s+(?:the\s+|my\s+|a\s+)?task\s+(.+?)"
        r"(?:\s+(?:as\s+)?(?:done|complete))?$",
        text,
    )
    if not complete_match:
        complete_match = re.search(r"\bmark\s+(.+?)\s+(?:as\s+)?(?:done|complete)$", text)
    if not complete_match:
        complete_match = re.search(
            r"\b(?:completed|finished)\s+(?:the\s+|my\s+|a\s+)?task\s+(.+)$", text
        )
    if complete_match:
        query = _clean_title(complete_match.group(1).strip())
        query = re.sub(r"\s+(?:as\s+)?(?:done|complete)$", "", query, flags=re.IGNORECASE).strip()
        return IntentResult(
            intent="complete_task",
            label=INTENT_LABELS["complete_task"],
            supported=True,
            confidence=0.89,
            entities={"title": query},
            explanation=(
                "Matched the task-completion rule. LifeDesk will match the task by title and "
                "propose marking it done for approval."
            ),
            matched_rule="complete_task / 'complete task'",
        )

    # --- send email --------------------------------------------------------
    if (
        EMAIL_ADDRESS.search(command)
        and "remind" not in text
        and re.search(r"\b(?:send|write|compose|email|mail)\b", text)
    ):
        recipients: list[str] = []
        for address in EMAIL_ADDRESS.findall(command):
            if address not in recipients:
                recipients.append(address)
        first = EMAIL_ADDRESS.search(command)
        rest = command[first.end():].strip(" .,:;-") if first else ""
        body_match = re.search(
            r"\b(?:saying|say|message(?:\s+is)?|body(?:\s+is)?|with\s+message)"
            r"\b[:\s]*(.+)$",
            rest,
            re.IGNORECASE | re.DOTALL,
        )
        body = (body_match.group(1).strip(" \"'“”‘’") if body_match else "").strip()
        subject_match = re.search(
            r"\bsubject\b[:\s]+(.+?)(?:\s+\b(?:saying|message|body)\b.*)?$",
            rest,
            re.IGNORECASE | re.DOTALL,
        )
        about_match = re.search(
            r"\babout\s+(.+?)(?:\s+\b(?:saying|message|body)\b.*)?$",
            rest,
            re.IGNORECASE | re.DOTALL,
        )
        if subject_match:
            subject = subject_match.group(1).strip(" \"'“”‘’")
        elif about_match:
            subject = about_match.group(1).strip(" \"'“”‘’")
        elif body:
            subject = body.splitlines()[0][:120]
        else:
            subject = "Message from LifeDesk"
        if not body:
            body = "Hi"
        if not subject:
            subject = "Message from LifeDesk"
        return IntentResult(
            intent="send_email",
            label=INTENT_LABELS["send_email"],
            supported=True,
            confidence=0.93,
            entities={
                "to": recipients,
                "subject": subject[:200],
                "body": body[:20000],
            },
            explanation=(
                "Matched the email rule. One email will be proposed for approval; nothing "
                "is sent until you approve and execute the workflow."
            ),
            matched_rule="send_email / 'send mail to <address>'",
        )

    # --- reminders ---------------------------------------------------------
    if re.search(r"\bremind(?:er)?\b", text) or "remind me" in text:
        title = ""
        remind_title = re.search(r"remind me (?:to|that|about)\s+(.+?)(?:\s+at\s+\d|\s+tomorrow|\s+in\s+\d|$)", text)
        if remind_title:
            title = _clean_title(remind_title.group(1))
        else:
            generic = re.search(r"(?:create|add|set)\s+(?:a\s+)?reminder(?:\s+(?:to|for|about))?\s*(.*)", text)
            if generic:
                title = _clean_title(generic.group(1))
        if not title:
            title = "Reminder"
        clock = extract_clock_time(text)
        relative = extract_relative_minutes(text)
        if relative:
            remind_at = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=relative)
        elif clock:
            remind_at = datetime.combine(target_date, clock)
        else:
            remind_at = datetime.now().replace(second=0, microsecond=0) + timedelta(hours=1)
        return IntentResult(
            intent="create_reminder",
            label=INTENT_LABELS["create_reminder"],
            supported=True,
            confidence=0.9,
            entities={"title": title, "remind_at": remind_at.isoformat(timespec="minutes")},
            explanation="Matched the reminder rule. A reminder will be proposed for approval.",
            matched_rule="create_reminder / 'remind'",
        )

    # --- study session -----------------------------------------------------
    if "study session" in text or ("study" in text and "schedule" in text):
        minutes = duration or 90
        return IntentResult(
            intent="schedule_study",
            label=INTENT_LABELS["schedule_study"],
            supported=True,
            confidence=0.92,
            entities={
                "date": target_date.isoformat(),
                "minutes": max(30, minutes),
                "topic": extract_study_topic(text) or "Focus",
            },
            explanation=(
                "Matched the study-session rule. LifeDesk will find the first conflict-free gap "
                "in the working window and propose one calendar block for approval."
            ),
            matched_rule="schedule_study / 'study session'",
        )

    # --- pending tasks -----------------------------------------------------
    if ("pending" in text and "task" in text) or text in {"pending tasks", "show pending", "what's pending"}:
        return IntentResult(
            intent="list_pending",
            label=INTENT_LABELS["list_pending"],
            supported=True,
            confidence=0.95,
            entities={"date": target_date.isoformat()},
            explanation="Read-only request. LifeDesk will return pending tasks from the local task provider. Nothing is executed.",
            matched_rule="list_pending / 'pending tasks'",
        )

    # --- meeting / event ---------------------------------------------------
    if "schedule" in text and re.search(r"\b(meeting|call|event|session|appointment|lecture)\b", text):
        raw_title = re.search(
            r"\b(?:schedule|book)\s+(?:a|an|the)?\s*(?:meeting|call|event|appointment|session)?\s*(?:with|about|for)?\s*(.*?)"
            r"(?:\s+(?:today|tomorrow|at\s+\d|on\s+monday|on\s+tuesday|on\s+wednesday|on\s+thursday|on\s+friday)|$)",
            text,
        )
        title = _clean_title(raw_title.group(1)) if raw_title else ""
        clock = extract_clock_time(text) or time(10, 0)
        if not title or title.lower() in {"meeting", "a meeting"}:
            title = "Meeting"
        return IntentResult(
            intent="schedule_event",
            label=INTENT_LABELS["schedule_event"],
            supported=True,
            confidence=0.85,
            entities={
                "title": title,
                "date": target_date.isoformat(),
                "start_time": clock.strftime("%H:%M"),
                "minutes": max(30, duration or 60),
            },
            explanation="Matched the scheduling rule. One calendar event will be proposed for approval.",
            matched_rule="schedule_event / 'schedule a meeting'",
        )

    # --- create task -------------------------------------------------------
    if "task" in text and re.search(r"\b(create|add|new)\b", text):
        raw_title = re.search(r"(?:create|add)\s+(?:a\s+)?task\s+(?:to\s+|called\s+|named\s+)?(.+?)(?:\s+(?:today|tomorrow)|\s+due\s+|$)", text)
        title = _clean_title(raw_title.group(1)) if raw_title else ""
        priority = "urgent" if "urgent" in text else "high" if "high priority" in text else "medium"
        return IntentResult(
            intent="create_task",
            label=INTENT_LABELS["create_task"],
            supported=True,
            confidence=0.84,
            entities={
                "title": title or "New task",
                "priority": priority,
                "due_date": target_date.isoformat() if re.search(r"today|tomorrow", text) else None,
            },
            explanation="Matched the task-creation rule. One pending task will be proposed for approval.",
            matched_rule="create_task / 'create a task'",
        )

    return IntentResult(
        intent="unsupported",
        label=INTENT_LABELS["unsupported"],
        supported=False,
        confidence=0.2,
        explanation=(
            "No deterministic rule matched this request. The prototype supports: plan my day, "
            "show pending tasks, schedule a study session, create or dismiss a reminder, schedule "
            "a meeting, create or complete a task, daily briefing, weekly review, find free time, "
            "and send an email. Nothing was executed."
        ),
        matched_rule="fallback",
    )
