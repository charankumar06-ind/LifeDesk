import os
import tempfile
from pathlib import Path

os.environ["LIFEDESK_DB"] = str(Path(tempfile.mkdtemp(prefix="lifedesk-tests-")) / "test.db")
os.environ["LIFEDESK_SEED"] = "0"
os.environ["LIFEDESK_PROVIDER_MODE"] = "local"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import get_db, init_db  # noqa: E402
from app.main import app  # noqa: E402

TABLES = ("actions", "activity", "workflows", "reminders", "tasks", "events")


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


AUTH_USER = "owner"
AUTH_PASSWORD = "test-password"


def _sign_in(client: TestClient) -> None:
    """Every test starts inside the authenticated workspace."""
    status = client.get("/api/auth/status")
    assert status.status_code == 200
    if not status.json()["configured"]:
        created = client.post(
            "/api/auth/setup",
            json={"username": AUTH_USER, "password": AUTH_PASSWORD},
        )
        assert created.status_code == 201, created.text
        return
    signed_in = client.post(
        "/api/auth/login",
        json={"username": AUTH_USER, "password": AUTH_PASSWORD},
    )
    if signed_in.status_code == 401:
        # A test may have changed the credential; reset the test workspace.
        with get_db() as conn:
            conn.execute("DELETE FROM auth_sessions")
            conn.execute("DELETE FROM auth_users")
        created = client.post(
            "/api/auth/setup",
            json={"username": AUTH_USER, "password": AUTH_PASSWORD},
        )
        assert created.status_code == 201, created.text
        return
    assert signed_in.status_code == 200, signed_in.text


@pytest.fixture(autouse=True)
def clean_db(client):
    init_db()
    with get_db() as conn:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
    _sign_in(client)
    yield
