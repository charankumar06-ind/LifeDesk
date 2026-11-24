"""Regression tests for the critical issues found in the engineering audit."""

from datetime import date, datetime, time, timedelta

from app.main import FRONTEND_DIST, resolve_frontend_file


def _iso(day_offset: int = 0, hour: int = 18, minute: int = 0) -> str:
    return datetime.combine(date.today() + timedelta(days=day_offset), time(hour, minute)).isoformat()


def _create_task(client, title="Regression task", **extra):
    payload = {"title": title, "priority": "high", "estimate_minutes": 60, **extra}
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_event(client, title="Regression event", start=None, end=None):
    payload = {
        "title": title,
        "start_at": start or _iso(0, 11),
        "end_at": end or _iso(0, 12),
        "kind": "meeting",
    }
    response = client.post("/api/events", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------- SPA traversal


def test_frontend_resolver_rejects_paths_outside_dist():
    assert resolve_frontend_file("../backend/lifedesk.db") is None
    assert resolve_frontend_file("../../README.md") is None
    assert resolve_frontend_file("assets/../../backend/lifedesk.db") is None
    assert resolve_frontend_file("api/does-not-exist") is None
    assert resolve_frontend_file("api") is None


def test_frontend_resolver_serves_bundled_assets_only():
    if not (FRONTEND_DIST / "index.html").exists():
        return  # no production build present; nothing to assert
    resolved = resolve_frontend_file("index.html")
    assert resolved is not None
    assert resolved.resolve() == (FRONTEND_DIST / "index.html").resolve()


def test_traversal_request_cannot_read_database(client):
    response = client.get("/..%2F..%2Fbackend%2Flifedesk.db")
    assert response.status_code == 404
    assert "sqlite" not in response.headers.get("content-type", "").lower()


def test_unknown_api_route_returns_json_404(client):
    response = client.get("/api/definitely-not-a-route")
    assert response.status_code == 404
    assert "application/json" in response.headers.get("content-type", "")


# ------------------------------------------------------------- null PATCH 422


def test_task_patch_rejects_explicit_nulls(client):
    task = _create_task(client, due_at=_iso(0, 20))
    for field in ("title", "description", "status", "priority", "estimate_minutes"):
        response = client.patch(f"/api/tasks/{task['id']}", json={field: None})
        assert response.status_code == 422, f"{field} -> {response.status_code}: {response.text}"


def test_task_nullable_fields_can_still_be_cleared(client):
    task = _create_task(client, due_at=_iso(0, 20), tags=["work"])
    response = client.patch(f"/api/tasks/{task['id']}", json={"due_at": None, "tags": None})
    assert response.status_code == 200
    assert response.json()["due_at"] is None
    assert response.json()["tags"] == []


def test_event_patch_rejects_explicit_nulls(client):
    event = _create_event(client)
    for field in ("title", "description", "start_at", "end_at", "location", "kind"):
        response = client.patch(f"/api/events/{event['id']}", json={field: None})
        assert response.status_code == 422, f"{field} -> {response.status_code}: {response.text}"


# ------------------------------------------------- approvals are not provider writes


def test_approval_decision_is_not_logged_as_provider_write(client):
    _create_task(client, title="Approval logging task", due_at=_iso(0, 20))
    workflow = client.post("/api/commands", json={"command": "Plan my day"}).json()
    assert workflow["actions"], workflow

    approved = client.post(f"/api/approvals/{workflow['id']}/decision", json={"decision": "approve"})
    assert approved.status_code == 200

    entries = client.get("/api/activity", params={"limit": 100}).json()["entries"]
    writes = [
        entry
        for entry in entries
        if entry["workflow_id"] == workflow["id"] and entry["operation"] == "create_event"
    ]
    assert writes == [], "approving must not log a provider write"

    decisions = [
        entry
        for entry in entries
        if entry["workflow_id"] == workflow["id"] and entry["operation"] == "approval_decision"
    ]
    assert len(decisions) == len(workflow["actions"])
    assert all(entry["provider_type"] == "workflow" for entry in decisions)

    executed = client.post(f"/api/approvals/{workflow['id']}/execute")
    assert executed.status_code == 200
    entries = client.get("/api/activity", params={"limit": 100}).json()["entries"]
    real_writes = [
        entry
        for entry in entries
        if entry["workflow_id"] == workflow["id"]
        and entry["operation"] == "create_event"
        and entry["status"] == "success"
    ]
    assert len(real_writes) == len(workflow["actions"])


# ------------------------------------------------ undecided actions are settled


def test_execute_settles_undecided_actions(client):
    for index in range(3):
        _create_task(client, title=f"Settle task {index}", due_at=_iso(0, 18 + index))

    workflow = client.post("/api/planner/propose", json={"date": date.today().isoformat()}).json()
    assert len(workflow["actions"]) >= 2, workflow

    first = workflow["actions"][0]["id"]
    decided = client.post(
        f"/api/approvals/{workflow['id']}/actions/{first}/decision",
        json={"decision": "approve"},
    )
    assert decided.status_code == 200

    response = client.post(f"/api/approvals/{workflow['id']}/execute")
    assert response.status_code == 200, response.text
    executed = response.json()

    assert executed["status"] == "completed"
    assert executed["result"]["skipped"] == len(workflow["actions"]) - 1
    assert all(action["status"] in {"executed", "rejected"} for action in executed["actions"])
    assert all(
        action["error"] for action in executed["actions"] if action["status"] == "rejected"
    )
    assert not any(action["status"] == "proposed" for action in executed["actions"])
    # Decisions are closed, so nothing was left changeable-but-unchangeable.
    assert client.post(
        f"/api/approvals/{workflow['id']}/actions/{workflow['actions'][1]['id']}/decision",
        json={"decision": "approve"},
    ).status_code == 409


# ------------------------------------------------- retry after a rejected plan


def test_rejected_plan_can_be_reproposed(client):
    _create_task(client, title="Retryable plan task", due_at=_iso(0, 17))

    first = client.post("/api/commands", json={"command": "Plan my day"}).json()
    assert first["status"] == "pending_approval"
    assert first["actions"]

    rejected = client.post(f"/api/approvals/{first['id']}/decision", json={"decision": "reject"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    second = client.post("/api/commands", json={"command": "Plan my day"}).json()
    assert second["status"] == "pending_approval", second.get("error")
    assert second["id"] != first["id"]
    assert second["actions"]

    # A second rejection must also be retryable (the dedupe key is handed back
    # each time rather than consumed once).
    assert client.post(
        f"/api/approvals/{second['id']}/decision", json={"decision": "reject"}
    ).status_code == 200
    third = client.post("/api/commands", json={"command": "Plan my day"}).json()
    assert third["status"] == "pending_approval", third.get("error")
    assert third["id"] not in {first["id"], second["id"]}
    assert third["actions"]


def test_pending_plan_still_blocks_identical_actions(client):
    _create_task(client, title="Still duplicate task", due_at=_iso(0, 16))
    first = client.post("/api/commands", json={"command": "Plan my day"}).json()
    assert first["status"] == "pending_approval"

    second = client.post("/api/commands", json={"command": "Plan my day"}).json()
    assert second["status"] == "failed"
    assert second["actions"] == []
    assert "duplicate" in (second["error"] or "").lower()
