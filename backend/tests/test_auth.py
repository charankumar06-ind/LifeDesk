from __future__ import annotations

from app.db import get_db

AUTH_USER = "owner"
AUTH_PASSWORD = "test-password"


def _wipe_auth() -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM auth_sessions")
        conn.execute("DELETE FROM auth_users")


def test_every_workspace_route_requires_login(client) -> None:
    client.cookies.clear()

    assert client.get("/api/health").status_code == 200
    status = client.get("/api/auth/status")
    assert status.status_code == 200
    assert status.json()["configured"] is True
    assert status.json()["authenticated"] is False

    for path in ("/api/dashboard", "/api/settings", "/api/automations", "/api/tasks"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert "Authentication required" in response.json()["detail"]

    assert client.post("/api/commands", json={"command": "Show pending tasks"}).status_code == 401
    assert client.get("/api/approvals").status_code == 401


def test_password_login_and_logout(client) -> None:
    client.cookies.clear()

    wrong = client.post(
        "/api/auth/login", json={"username": AUTH_USER, "password": "wrong-password"}
    )
    assert wrong.status_code == 401
    assert "Incorrect" in wrong.json()["detail"]

    signed_in = client.post(
        "/api/auth/login", json={"username": AUTH_USER, "password": AUTH_PASSWORD}
    )
    assert signed_in.status_code == 200
    body = signed_in.json()
    assert body["authenticated"] is True
    assert body["user"]["username"] == AUTH_USER
    assert "lifedesk_session" in client.cookies

    set_cookie = signed_in.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie

    assert client.get("/api/dashboard").status_code == 200
    assert client.get("/api/settings").status_code == 200

    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/dashboard").status_code == 401


def test_logout_revokes_the_server_side_session(client) -> None:
    client.cookies.clear()
    assert client.post(
        "/api/auth/login", json={"username": AUTH_USER, "password": AUTH_PASSWORD}
    ).status_code == 200
    stolen_token = client.cookies.get("lifedesk_session")
    assert stolen_token

    assert client.post("/api/auth/logout").status_code == 200

    # Replaying the old cookie must fail: the token hash is gone server-side.
    client.cookies.set("lifedesk_session", stolen_token)
    assert client.get("/api/dashboard").status_code == 401


def test_first_run_setup_is_one_time_and_stores_a_hash(client) -> None:
    _wipe_auth()
    client.cookies.clear()

    status = client.get("/api/auth/status").json()
    assert status["configured"] is False
    assert status["authenticated"] is False

    short = client.post(
        "/api/auth/setup", json={"username": AUTH_USER, "password": "short"}
    )
    assert short.status_code == 422

    created = client.post(
        "/api/auth/setup",
        json={"username": "  Owner  ", "display_name": "  Ari Mensha  ", "password": AUTH_PASSWORD},
    )
    assert created.status_code == 201, created.text
    settings = client.get("/api/settings").json()
    assert settings["display_name"] == "Ari Mensha"
    assert created.json()["authenticated"] is True
    assert created.json()["user"]["username"] == "Owner"
    assert client.get("/api/dashboard").status_code == 200

    with get_db() as conn:
        row = conn.execute(
            "SELECT username, password_hash, salt, iterations FROM auth_users"
        ).fetchone()
        session = conn.execute("SELECT token_hash FROM auth_sessions").fetchone()
    assert row["username"] == "Owner"
    assert row["password_hash"] != AUTH_PASSWORD
    assert len(row["password_hash"]) == 64
    assert row["salt"] and row["iterations"] >= 200_000
    assert session["token_hash"] != client.cookies.get("lifedesk_session")

    duplicate = client.post(
        "/api/auth/setup", json={"username": "second", "password": "another-password"}
    )
    assert duplicate.status_code == 409

    # Leave the fixture's expected credential in place for following tests.
    assert client.post("/api/auth/logout").status_code == 200
    assert client.post(
        "/api/auth/login", json={"username": "Owner", "password": AUTH_PASSWORD}
    ).status_code == 200


def test_profile_name_is_dynamic_after_setup(client) -> None:
    _wipe_auth()
    client.cookies.clear()

    created = client.post(
        "/api/auth/setup",
        json={
            "username": AUTH_USER,
            "display_name": "Ari Mensha",
            "password": AUTH_PASSWORD,
        },
    )
    assert created.status_code == 201, created.text
    assert client.get("/api/settings").json()["display_name"] == "Ari Mensha"
    assert client.get("/api/dashboard").json()["settings"]["display_name"] == "Ari Mensha"

    current = client.get("/api/settings").json()
    updated = client.put(
        "/api/settings", json={**current, "display_name": "Ari M. Mensha"}
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Ari M. Mensha"
    assert client.get("/api/dashboard").json()["settings"]["display_name"] == "Ari M. Mensha"

    # Keep the fixture credential valid for the next test.
    assert client.post("/api/auth/logout").status_code == 200
    assert client.post(
        "/api/auth/login", json={"username": AUTH_USER, "password": AUTH_PASSWORD}
    ).status_code == 200


def test_seeded_profile_placeholder_is_migrated_once(client) -> None:
    from app.db import get_db
    from app.services.settings import (
        PROFILE_NAME_MIGRATION_KEY,
        migrate_seeded_profile_name,
    )

    def reset_migration() -> None:
        with get_db() as conn:
            conn.execute(
                "DELETE FROM meta WHERE key = ?", (PROFILE_NAME_MIGRATION_KEY,)
            )

    reset_migration()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('display_name', 'Ari Mensah')"
            " ON CONFLICT(key) DO UPDATE SET value = 'Ari Mensah'"
        )
    migrate_seeded_profile_name()
    assert client.get("/api/settings").json()["display_name"] == "Ari Mensha"

    # The old placeholder can be chosen deliberately later; the one-time
    # migration must not rewrite it again.
    with get_db() as conn:
        conn.execute(
            "UPDATE settings SET value = 'Ari Mensah' WHERE key = 'display_name'"
        )
    migrate_seeded_profile_name()
    assert client.get("/api/settings").json()["display_name"] == "Ari Mensah"

    # A custom name is also left alone.
    reset_migration()
    with get_db() as conn:
        conn.execute(
            "UPDATE settings SET value = 'Custom Owner' WHERE key = 'display_name'"
        )
    migrate_seeded_profile_name()
    assert client.get("/api/settings").json()["display_name"] == "Custom Owner"


def test_rate_limit_blocks_repeated_guessing(client) -> None:
    client.cookies.clear()
    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"username": AUTH_USER, "password": "definitely-wrong"},
        )
        assert response.status_code == 401
    blocked = client.post(
        "/api/auth/login", json={"username": AUTH_USER, "password": "definitely-wrong"}
    )
    assert blocked.status_code == 429

    # A correct password clears the counter once the window allows it; the
    # throttle is per username, so verify the account still works afterward.
    from app.security import _clear_failures

    _clear_failures(AUTH_USER)
    assert client.post(
        "/api/auth/login", json={"username": AUTH_USER, "password": AUTH_PASSWORD}
    ).status_code == 200
