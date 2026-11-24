from datetime import date, datetime, time, timedelta

DEMO_COMMAND = (
    "Plan my day. I have two pending assignments and need a two-hour Python study session."
)


def _iso(day_offset: int, hour: int, minute: int = 0) -> str:
    return datetime.combine(date.today() + timedelta(days=day_offset), time(hour, minute)).isoformat()


def _create_task(client, title="Data structures assignment", priority="urgent", estimate=90, due=None, **extra):
    payload = {
        "title": title,
        "priority": priority,
        "estimate_minutes": estimate,
        "due_at": due,
        "tags": ["Coursework"],
        **extra,
    }
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_event(client, title="Research methods lecture", start=None, end=None):
    payload = {
        "title": title,
        "start_at": start or _iso(0, 11, 0),
        "end_at": end or _iso(0, 12, 0),
        "kind": "meeting",
    }
    response = client.post("/api/events", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_system_declare_demo_mode(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    system = client.get("/api/system").json()
    assert system["demo_mode"] is True
    assert system["demo_label"] == "Demo Mode — Local Data"
    assert system["ai"]["mode"] == "deterministic"
    assert system["ai"]["llm_configured"] is False
    assert all(provider["kind"] == "local" for provider in system["providers"])


def test_task_crud_and_filters(client):
    created = _create_task(client, title="Write thesis outline", priority="high")
    assert created["status"] == "todo"

    updated = client.patch(f"/api/tasks/{created['id']}", json={"status": "done", "priority": "urgent"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "done"
    assert updated.json()["completed_at"] is not None

    reopened = client.patch(f"/api/tasks/{created['id']}", json={"status": "todo"})
    assert reopened.json()["completed_at"] is None

    assert client.get("/api/tasks", params={"priority": "urgent"}).json()["tasks"]
    assert client.get("/api/tasks", params={"search": "thesis"}).json()["tasks"]
    assert client.get("/api/tasks", params={"status": "done"}).json()["tasks"] == []
    assert client.get("/api/tasks", params={"status": "bogus"}).status_code == 422
    assert client.post("/api/tasks", json={"title": "", "estimate_minutes": 60}).status_code == 422
    assert client.post("/api/tasks", json={"title": "x", "estimate_minutes": 5}).status_code == 422

    deleted = client.delete(f"/api/tasks/{created['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/api/tasks/{created['id']}").status_code == 404


def test_event_crud_and_validation(client):
    event = _create_event(client)
    assert event["source"] == "local"

    patched = client.patch(f"/api/events/{event['id']}", json={"title": "Lecture moved", "start_at": _iso(0, 13, 0), "end_at": _iso(0, 14, 0)})
    assert patched.status_code == 200
    assert patched.json()["title"] == "Lecture moved"
    assert patched.json()["start_at"].startswith(_iso(0, 13, 0)[:16])

    invalid = client.post("/api/events", json={"title": "Bad", "start_at": _iso(0, 12, 0), "end_at": _iso(0, 11, 0)})
    assert invalid.status_code == 422
    invalid_patch = client.patch(f"/api/events/{event['id']}", json={"end_at": _iso(0, 12, 0)})
    assert invalid_patch.status_code == 422

    listed = client.get("/api/events", params={"start": date.today().isoformat(), "end": (date.today() + timedelta(days=1)).isoformat()})
    assert len(listed.json()["events"]) == 1

    assert client.delete(f"/api/events/{event['id']}").status_code == 200
    assert client.delete(f"/api/events/{event['id']}").status_code == 404


def test_demo_acceptance_flow(client):
    """Acceptance test: plan my day -> approve -> execute -> calendar + history."""
    _create_task(client, title="Assignment 1 — algorithms proofs", due=_iso(0, 23, 0))
    _create_task(client, title="Assignment 2 — research essay", priority="high", due=_iso(1, 17, 0))
    _create_event(client, start=_iso(0, 11, 0), end=_iso(0, 12, 0))

    response = client.post("/api/commands", json={"command": DEMO_COMMAND})
    assert response.status_code == 201, response.text
    workflow = response.json()
    assert workflow["intent"] == "plan_day"
    assert workflow["status"] == "pending_approval"
    assert len(workflow["actions"]) >= 2
    assert all(action["status"] == "proposed" for action in workflow["actions"])
    assert any("study" in action["title"].lower() for action in workflow["actions"])
    assert workflow["plan"]["ai"]["llm_used"] is False
    assert any(step["title"] == "Read pending tasks" for step in workflow["plan"]["steps"])

    study_action = next(action for action in workflow["actions"] if "study" in action["title"].lower())
    study_start = datetime.fromisoformat(study_action["payload"]["start_at"])
    study_end = datetime.fromisoformat(study_action["payload"]["end_at"])
    assert (study_end - study_start) == timedelta(hours=2)

    # Nothing is written before approval.
    today_events = client.get(
        "/api/events",
        params={"start": date.today().isoformat(), "end": (date.today() + timedelta(days=1)).isoformat()},
    ).json()["events"]
    assert len(today_events) == 1

    approved = client.post(f"/api/approvals/{workflow['id']}/decision", json={"decision": "approve"})
    assert approved.status_code == 200
    assert {action["status"] for action in approved.json()["actions"]} == {"approved"}

    executed = client.post(f"/api/approvals/{workflow['id']}/execute")
    assert executed.status_code == 200, executed.text
    executed_workflow = executed.json()
    assert executed_workflow["status"] == "completed"
    assert {action["status"] for action in executed_workflow["actions"]} == {"executed"}

    today_events = client.get(
        "/api/events",
        params={"start": date.today().isoformat(), "end": (date.today() + timedelta(days=1)).isoformat()},
    ).json()["events"]
    assert len(today_events) == 1 + len(workflow["actions"])
    assert any(event["kind"] == "study" for event in today_events)

    history = client.get("/api/activity", params={"limit": 50}).json()
    created = [entry for entry in history["entries"] if entry["operation"] == "create_event" and entry["status"] == "success"]
    assert created
    assert all(entry["simulated"] is True for entry in created)
    assert all(entry["provider_name"] == "local-calendar" for entry in created)
    assert any(entry["provider_type"] == "workflow" for entry in history["entries"])

    # Duplicate execution is blocked.
    assert client.post(f"/api/approvals/{workflow['id']}/execute").status_code == 409
    assert client.post(f"/api/approvals/{workflow['id']}/decision", json={"decision": "approve"}).status_code == 409


def test_rejection_prevents_execution(client):
    _create_task(client)
    workflow = client.post("/api/commands", json={"command": "Plan my day"}).json()
    rejected = client.post(f"/api/approvals/{workflow['id']}/decision", json={"decision": "reject"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    assert client.post(f"/api/approvals/{workflow['id']}/execute").status_code == 409
    events = client.get(
        "/api/events",
        params={"start": date.today().isoformat(), "end": (date.today() + timedelta(days=1)).isoformat()},
    ).json()["events"]
    assert events == []
    activity = client.get("/api/activity").json()["entries"]
    assert any(entry["status"] == "rejected" for entry in activity)


def test_pending_tasks_command_is_read_only(client):
    _create_task(client, title="Pending one")
    _create_task(client, title="Pending two", priority="low")
    workflow = client.post("/api/commands", json={"command": "Show pending tasks"}).json()
    assert workflow["intent"] == "list_pending"
    assert workflow["status"] == "completed"
    assert workflow["result"]["count"] == 2
    assert workflow["actions"] == []
    activity = client.get("/api/activity").json()["entries"]
    assert any(entry["operation"] == "list_tasks" and entry["status"] == "success" for entry in activity)


def test_reminder_flow(client):
    workflow = client.post("/api/commands", json={"command": "Remind me to submit the course form at 17:00"}).json()
    assert workflow["intent"] == "create_reminder"
    action = workflow["actions"][0]
    assert action["action_type"] == "create_reminder"
    assert "course form" in action["title"].lower()

    client.post(f"/api/approvals/{workflow['id']}/decision", json={"decision": "approve"})
    executed = client.post(f"/api/approvals/{workflow['id']}/execute")
    assert executed.status_code == 200

    reminders = client.get("/api/reminders", params={"status": "pending"}).json()["reminders"]
    assert len(reminders) == 1
    assert client.post(f"/api/reminders/{reminders[0]['id']}/dismiss").status_code == 200
    assert client.get("/api/reminders", params={"status": "pending"}).json()["reminders"] == []


def test_study_session_command(client):
    workflow = client.post(
        "/api/commands", json={"command": "Schedule a two-hour Python study session"}
    ).json()
    assert workflow["intent"] == "schedule_study"
    action = workflow["actions"][0]
    assert "python" in action["title"].lower()
    start = datetime.fromisoformat(action["payload"]["start_at"])
    end = datetime.fromisoformat(action["payload"]["end_at"])
    assert end - start == timedelta(hours=2)

    client.post(f"/api/approvals/{workflow['id']}/decision", json={"decision": "approve"})
    assert client.post(f"/api/approvals/{workflow['id']}/execute").status_code == 200
    events = client.get(
        "/api/events",
        params={"start": date.today().isoformat(), "end": (date.today() + timedelta(days=1)).isoformat()},
    ).json()["events"]
    assert len(events) == 1
    assert events[0]["kind"] == "study"


def test_unsupported_command_logs_failed_attempt(client):
    workflow = client.post("/api/commands", json={"command": "Book a flight to Tokyo"}).json()
    assert workflow["status"] == "failed"
    assert workflow["actions"] == []
    activity = client.get("/api/activity").json()["entries"]
    assert activity[0]["status"] == "failed"
    assert activity[0]["provider_type"] == "ai"


def test_duplicate_actions_are_blocked(client):
    first = client.post("/api/commands", json={"command": DEMO_COMMAND}).json()
    assert first["status"] == "pending_approval"
    second = client.post("/api/commands", json={"command": DEMO_COMMAND}).json()
    assert second["status"] == "failed"
    assert "duplicate" in (second["error"] or "").lower() or "already" in (second["error"] or "").lower()


def test_planner_endpoint_and_handoff(client):
    _create_task(client, title="Planner task", due=_iso(0, 22, 0))
    _create_event(client)
    plan = client.get("/api/planner/day", params={"date": date.today().isoformat()})
    assert plan.status_code == 200
    body = plan.json()
    assert body["plan"]["blocks"]
    assert any(block["type"] == "event" for block in body["plan"]["blocks"])
    assert any(block["type"] == "task" for block in body["plan"]["blocks"])
    assert body["plan"]["rationale"]

    proposal = client.post("/api/planner/propose", json={"date": date.today().isoformat()})
    assert proposal.status_code == 201
    workflow = proposal.json()
    assert workflow["status"] == "pending_approval"
    assert workflow["actions"]


def test_settings_validation_and_persistence(client):
    current = client.get("/api/settings").json()
    assert current["time_format"] == "24h"

    updated = client.put(
        "/api/settings",
        json={**current, "display_name": "Nadia Okafor", "time_format": "12h", "day_start": "07:30", "day_end": "20:00"},
    )
    assert updated.status_code == 200
    assert updated.json()["time_format"] == "12h"
    assert client.get("/api/settings").json()["display_name"] == "Nadia Okafor"

    invalid = client.put("/api/settings", json={**current, "day_start": "7:30 am"})
    assert invalid.status_code == 422


def test_dashboard_aggregates_local_data(client):
    _create_task(client, title="Open task")
    _create_event(client)
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["stats"]["pending_count"] == 1
    assert len(dashboard["events_today"]) == 1
    assert dashboard["settings"]["time_format"] in {"12h", "24h"}
    assert len(dashboard["stats"]["weekly_completions"]) == 7


def test_planner_does_not_duplicate_an_executed_focus_block(client):
    task = _create_task(client, title="Planner duplicate guard", due=_iso(0, 20, 0), estimate=60)
    workflow = client.post("/api/commands", json={"command": "Plan my day"}).json()
    client.post(f"/api/approvals/{workflow['id']}/decision", json={"decision": "approve"})
    assert client.post(f"/api/approvals/{workflow['id']}/execute").status_code == 200

    plan = client.get("/api/planner/day", params={"date": date.today().isoformat()}).json()["plan"]
    matches = [block for block in plan["blocks"] if task["title"] in block["title"]]
    assert len(matches) == 1
    assert matches[0]["type"] == "event"
    assert any("Already scheduled today" in reason for reason in plan["rationale"])
