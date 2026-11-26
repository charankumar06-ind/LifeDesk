from __future__ import annotations

import sys
from datetime import datetime, timedelta

import pytest

from app.config import BACKEND_DIR
from app.domain import EmailMessage, EventCreate, EventUpdate, ReminderCreate, TaskCreate, TaskUpdate
from app.providers.base import ProviderError, ProviderInfo, ProviderNotConfigured
from app.providers.mcp_adapter import (
    McpCalendarProvider,
    McpMailProvider,
    McpReminderProvider,
    McpTaskProvider,
)
from app.providers.mcp_client import McpClient, McpSettings
from app.providers.registry import build_services


def info(kind: str) -> ProviderInfo:
    return ProviderInfo(
        key=f"mcp-{kind}",
        label=kind,
        kind="mcp",
        transport="stdio",
        status="connected",
        note="test",
    )


class FakeClient:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        self.calls.append((name, arguments or {}))
        return self.responses[name]


def event_row(**overrides) -> dict:
    now = datetime(2026, 11, 25, 9, 0)
    row = {
        "id": "evt_1",
        "title": "MCP event",
        "description": "",
        "start_at": now.isoformat(),
        "end_at": (now + timedelta(hours=1)).isoformat(),
        "location": "",
        "kind": "meeting",
        "source": "mcp",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    row.update(overrides)
    return row


def task_row(**overrides) -> dict:
    now = datetime(2026, 11, 25, 9, 0)
    row = {
        "id": "tsk_1",
        "title": "MCP task",
        "description": "",
        "status": "todo",
        "priority": "high",
        "due_at": None,
        "estimate_minutes": 60,
        "tags": [],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "completed_at": None,
    }
    row.update(overrides)
    return row


def reminder_row(**overrides) -> dict:
    now = datetime(2026, 11, 25, 9, 0)
    row = {
        "id": "rem_1",
        "title": "MCP reminder",
        "note": "",
        "remind_at": now.isoformat(),
        "status": "pending",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    row.update(overrides)
    return row


def test_calendar_provider_maps_contract() -> None:
    client = FakeClient(
        {
            "calendar_list_events": {"events": [event_row()]},
            "calendar_get_event": {"event": event_row()},
            "calendar_create_event": {"event": event_row(source="workflow")},
            "calendar_update_event": {"event": event_row(title="Updated")},
            "calendar_delete_event": {"deleted": False},
        }
    )
    provider = McpCalendarProvider(client, info("calendar"))
    start = datetime(2026, 11, 25, 0, 0)
    end = start + timedelta(days=1)

    assert len(provider.list_events(start, end)) == 1
    assert provider.get_event("evt_1") is not None
    created = provider.create_event(
        EventCreate(
            title="MCP event",
            start_at=start + timedelta(hours=9),
            end_at=start + timedelta(hours=10),
        ),
        source="workflow",
    )
    assert created.source == "workflow"
    assert client.calls[2][0] == "calendar_create_event"
    assert client.calls[2][1]["source"] == "workflow"

    updated = provider.update_event("evt_1", EventUpdate(title="Updated"))
    assert updated.title == "Updated"
    assert client.calls[3] == ("calendar_update_event", {"event_id": "evt_1", "fields": {"title": "Updated"}})

    with pytest.raises(KeyError):
        provider.delete_event("evt_missing")


def test_task_and_reminder_provider_maps_contract() -> None:
    client = FakeClient(
        {
            "tasks_list": {"tasks": [task_row()]},
            "tasks_get": {"task": task_row()},
            "tasks_create": {"task": task_row()},
            "tasks_update": {"task": task_row(status="done")},
            "tasks_delete": {"deleted": True},
            "reminders_list": {"reminders": [reminder_row()]},
            "reminders_create": {"reminder": reminder_row()},
            "reminders_dismiss": {"reminder": reminder_row(status="dismissed")},
        }
    )
    tasks = McpTaskProvider(client, info("tasks"))
    reminders = McpReminderProvider(client, info("reminders"))

    assert tasks.list_tasks(status="open")[0].id == "tsk_1"
    assert client.calls[0] == ("tasks_list", {"status": "open"})
    assert tasks.create_task(TaskCreate(title="MCP task")).priority == "high"
    assert tasks.update_task("tsk_1", TaskUpdate(status="done")).status == "done"
    assert tasks.update_task("tsk_1", TaskUpdate(due_at=None)).id == "tsk_1"

    assert reminders.list_reminders(status="pending")[0].status == "pending"
    assert reminders.create_reminder(
        ReminderCreate(title="MCP reminder", remind_at=datetime(2026, 11, 25, 9, 0))
    ).id == "rem_1"
    assert reminders.dismiss_reminder("rem_1").status == "dismissed"


def test_mail_provider_maps_smtp_contract() -> None:
    client = FakeClient(
        {"mail_send": {"sent": True, "to": ["vishnuvardhan7219@gmail.com"], "subject": "HI"}}
    )
    provider = McpMailProvider(client, info("mail"))
    result = provider.send_email(
        EmailMessage(to=["vishnuvardhan7219@gmail.com"], subject="HI", body="HI")
    )

    assert result["sent"] is True
    assert client.calls == [
        (
            "mail_send",
            {"to": ["vishnuvardhan7219@gmail.com"], "subject": "HI", "body": "HI"},
        )
    ]


def test_mail_provider_rejects_unconfirmed_delivery() -> None:
    provider = McpMailProvider(FakeClient({"mail_send": {"sent": False}}), info("mail"))
    with pytest.raises(ProviderError):
        provider.send_email(EmailMessage(to=["a@b.com"], subject="HI", body="HI"))


def test_mcp_startup_failure_falls_back_to_local(monkeypatch) -> None:
    monkeypatch.setenv("LIFEDESK_MCP_FALLBACK", "local")

    def fail(self):
        raise ProviderError("server unavailable")

    monkeypatch.setattr(McpClient, "probe", fail)
    services = build_services("mcp")

    assert services.mode == "local-fallback"
    assert services.calendar.info.kind == "local"
    assert services.runtime["fallback_active"] is True
    assert "server unavailable" in services.runtime["error"]


def test_mcp_startup_failure_can_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("LIFEDESK_MCP_FALLBACK", "error")

    def fail(self):
        raise ProviderError("server unavailable")

    monkeypatch.setattr(McpClient, "probe", fail)
    with pytest.raises(ProviderNotConfigured):
        build_services("mcp")


def test_system_reports_live_mcp_status(client) -> None:
    from app.providers.registry import Services, get_services, set_services
    from app.providers.local_calendar import LocalCalendarProvider
    from app.providers.local_mail import LocalMailProvider
    from app.providers.local_reminder import LocalReminderProvider
    from app.providers.local_task import LocalTaskProvider

    original = get_services()
    set_services(
        Services(
            calendar=LocalCalendarProvider(),
            tasks=LocalTaskProvider(),
            reminders=LocalReminderProvider(),
            mail=LocalMailProvider(),
            mode="mcp",
            runtime={
                "configured": True,
                "transport": "stdio",
                "endpoint": "LifeDesk reference MCP server",
                "status": "connected",
                "tools": ["calendar_list_events"],
            },
        )
    )
    try:
        body = client.get("/api/system").json()
    finally:
        set_services(original)

    assert body["provider_mode"] == "mcp"
    assert body["mcp"]["status"] == "connected"
    assert body["mcp"]["fallback_active"] is False
    assert body["integrations"][0]["status"] == "connected"


def test_runtime_health_degrades_and_recovers(client, monkeypatch) -> None:
    from app.providers.mcp_adapter import REQUIRED_TOOLS
    from app.providers.registry import get_services, set_services

    monkeypatch.setenv("LIFEDESK_MCP_FALLBACK", "local")
    monkeypatch.setattr(
        McpClient, "probe", lambda self: sorted(REQUIRED_TOOLS | {"mail_send"})
    )
    state = {"fail": True}

    def call_tool(self, name, arguments=None):
        if state["fail"]:
            raise ProviderError("bridge offline")
        return {"tasks": []}

    monkeypatch.setattr(McpClient, "call_tool", call_tool)

    original = get_services()
    services = build_services("mcp")
    set_services(services)
    try:
        with pytest.raises(ProviderError):
            services.tasks.list_tasks()

        # A runtime failure degrades health; it never switches providers.
        assert services.mode == "mcp"
        assert services.tasks.info.kind == "mcp"
        assert services.runtime["status"] == "error"
        assert services.runtime["fallback_active"] is False
        assert "bridge offline" in services.runtime["error"]

        degraded = client.get("/api/system").json()
        assert degraded["provider_mode"] == "mcp"
        assert degraded["mcp"]["status"] == "error"
        assert degraded["mcp"]["fallback_active"] is False
        assert degraded["integrations"][0]["status"] == "error"
        assert all(
            provider["status"] == "error"
            for provider in degraded["providers"]
            if provider["kind"] == "mcp"
        )

        # The next successful call restores runtime health.
        state["fail"] = False
        assert services.tasks.list_tasks() == []
        assert services.runtime["status"] == "connected"
        assert services.runtime["error"] is None

        recovered = client.get("/api/system").json()
        assert recovered["mcp"]["status"] == "connected"
        assert recovered["integrations"][0]["status"] == "connected"
        assert all(
            provider["status"] == "connected"
            for provider in recovered["providers"]
            if provider["kind"] == "mcp"
        )
    finally:
        set_services(original)


def test_mcp_without_mail_tool_starts_with_email_unavailable(client, monkeypatch) -> None:
    from app.providers.mcp_adapter import REQUIRED_TOOLS
    from app.providers.registry import get_services, set_services

    monkeypatch.setenv("LIFEDESK_MCP_FALLBACK", "error")
    # A valid MCP server that implements the required contract but not email.
    monkeypatch.setattr(McpClient, "probe", lambda self: sorted(REQUIRED_TOOLS))
    monkeypatch.setattr(McpClient, "call_tool", lambda self, name, arguments=None: {"tasks": []})

    original = get_services()
    services = build_services("mcp")
    set_services(services)
    try:
        assert services.mode == "mcp"
        assert services.mail.info.status == "not_configured"
        assert services.runtime["mail_available"] is False
        assert services.runtime["mail_configured"] is None

        body = client.get("/api/system").json()
        assert body["provider_mode"] == "mcp"
        assert body["mcp"]["status"] == "connected"
        assert body["mcp"]["mail_available"] is False
        assert body["mcp"]["mail_configured"] is None
        assert all(provider["kind"] == "mcp" for provider in body["providers"])

        mail_provider = next(p for p in body["providers"] if p["key"] == "mcp-mail")
        assert mail_provider["status"] == "not_configured"
        assert "mail_send" in mail_provider["note"]

        email = next(i for i in body["integrations"] if i["name"].startswith("Email"))
        assert email["status"] == "not_configured"
        assert "mail_send" in email["detail"]

        # Non-mail providers still work; only email is unavailable.
        assert services.tasks.list_tasks(status="open") == []
        with pytest.raises(ProviderError, match="mail_send"):
            services.mail.send_email(EmailMessage(to=["a@b.com"], subject="HI", body="HI"))
    finally:
        set_services(original)


def test_reference_mail_status_reports_missing_credentials(monkeypatch) -> None:
    from mcp_server import server as reference

    monkeypatch.delenv("LIFEDESK_SMTP_USER", raising=False)
    monkeypatch.delenv("LIFEDESK_SMTP_PASSWORD", raising=False)

    assert reference.mail_status()["configured"] is False
    with pytest.raises(RuntimeError, match="LIFEDESK_SMTP_USER"):
        reference.mail_send(["friend@example.com"], "HI", "HI")


def test_reference_mail_send_uses_smtp(monkeypatch) -> None:
    from mcp_server import server as reference

    monkeypatch.setenv("LIFEDESK_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("LIFEDESK_SMTP_PORT", "587")
    monkeypatch.setenv("LIFEDESK_SMTP_USER", "sender@example.com")
    monkeypatch.setenv("LIFEDESK_SMTP_PASSWORD", "app password")
    monkeypatch.setenv("LIFEDESK_SMTP_FROM", "sender@example.com")

    sent: dict = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ehlo(self):
            pass

        def starttls(self):
            sent["starttls"] = True

        def login(self, user, password):
            sent["login"] = (user, password)

        def send_message(self, message):
            sent["message"] = message

    monkeypatch.setattr(reference.smtplib, "SMTP", FakeSMTP)
    result = reference.mail_send(["friend@example.com"], "HI", "HI")

    assert result["sent"] is True
    assert result["to"] == ["friend@example.com"]
    assert sent["host"] == "smtp.example.com"
    assert sent["port"] == 587
    assert sent["starttls"] is True
    assert sent["login"] == ("sender@example.com", "app password")
    assert sent["message"]["Subject"] == "HI"
    assert sent["message"]["To"] == "friend@example.com"
    assert sent["message"].get_content().strip() == "HI"


def test_reference_mcp_server_stdio_round_trip() -> None:
    settings = McpSettings(
        transport="stdio",
        command=sys.executable,
        args=("-m", "mcp_server.server"),
        cwd=str(BACKEND_DIR),
        timeout=30,
    )
    client = McpClient(settings)
    tools = client.probe()

    assert "calendar_list_events" in tools
    assert "tasks_create" in tools
    assert "mail_send" in tools
    status = client.call_tool("lifedesk_status")
    assert status["server"] == "lifedesk-reference"
    assert "events" in status["counts"]
