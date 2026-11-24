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


@pytest.fixture(autouse=True)
def clean_db(client):
    init_db()
    with get_db() as conn:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
    yield
