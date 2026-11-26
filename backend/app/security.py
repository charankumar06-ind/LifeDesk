"""Local single-user authentication.

LifeDesk is local-first, so the safest default is a workspace password that
never leaves the machine. Credentials are stored as PBKDF2-HMAC-SHA256 hashes
with a random salt; sessions are random tokens whose SHA-256 hash is stored in
SQLite. The browser receives only an HttpOnly cookie.

There is intentionally no "skip login" path: every API route except the auth
handshake and a minimal health probe requires a valid session.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any

from .db import get_db
from .utils import iso, new_id, now

COOKIE_NAME = "lifedesk_session"
PBKDF2_ITERATIONS = 240_000
MIN_PASSWORD_LENGTH = 8
SESSION_DAYS = max(1, min(int(os.environ.get("LIFEDESK_SESSION_DAYS", "7") or 7), 30))
COOKIE_SECURE = os.environ.get("LIFEDESK_COOKIE_SECURE", "0").strip() == "1"

#: Five failed attempts per username/IP per five minutes. In-memory is enough
#: for a local single-process app and avoids a password-guessing free-for-all.
MAX_FAILED_ATTEMPTS = 5
FAILURE_WINDOW_SECONDS = 300
_failures: dict[str, list[float]] = {}


class AuthError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #


def _hash_password(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations
    ).hex()


def hash_password(password: str) -> tuple[str, str, int]:
    salt = secrets.token_hex(16)
    return _hash_password(password, salt, PBKDF2_ITERATIONS), salt, PBKDF2_ITERATIONS


def _session_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #


def _validate_credentials(username: str, password: str) -> tuple[str, str]:
    username = (username or "").strip()
    if not username or len(username) > 64:
        raise AuthError("Username must be between 1 and 64 characters.", 422)
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise AuthError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", 422
        )
    if len(password) > 200:
        raise AuthError("Password is too long.", 422)
    if password.lower() == username.lower():
        raise AuthError("Password cannot be the same as the username.", 422)
    return username, password


def has_user() -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM auth_users LIMIT 1").fetchone()
    return row is not None


def create_user(username: str, password: str) -> dict[str, Any]:
    username, password = _validate_credentials(username, password)
    if has_user():
        raise AuthError("This workspace is already configured. Sign in instead.", 409)
    password_hash, salt, iterations = hash_password(password)
    user_id = new_id("usr")
    stamp = iso(now())
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO auth_users (id, username, password_hash, salt, iterations,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, password_hash, salt, iterations, stamp, stamp),
            )
    except sqlite3.IntegrityError as exc:
        raise AuthError("That username is already taken.", 409) from exc
    return {"id": user_id, "username": username, "created_at": stamp}


def _find_user(username: str) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute(
            "SELECT id, username, password_hash, salt, iterations, created_at"
            " FROM auth_users WHERE username = ? COLLATE NOCASE",
            (username.strip(),),
        ).fetchone()


def _throttle_key(username: str) -> str:
    return username.strip().lower()


def _check_throttle(username: str) -> None:
    key = _throttle_key(username)
    cutoff = time.monotonic() - FAILURE_WINDOW_SECONDS
    recent = [stamp for stamp in _failures.get(key, []) if stamp >= cutoff]
    _failures[key] = recent
    if len(recent) >= MAX_FAILED_ATTEMPTS:
        raise AuthError(
            "Too many failed sign-in attempts. Wait a few minutes and try again.", 429
        )


def _record_failure(username: str) -> None:
    key = _throttle_key(username)
    _failures.setdefault(key, []).append(time.monotonic())


def _clear_failures(username: str) -> None:
    _failures.pop(_throttle_key(username), None)


def authenticate(username: str, password: str) -> dict[str, Any]:
    _check_throttle(username)
    row = _find_user(username)
    candidate = ""
    if row is not None:
        candidate = _hash_password(password or "", row["salt"], row["iterations"])
    valid = bool(row) and hmac.compare_digest(candidate, row["password_hash"])
    if not valid:
        _record_failure(username)
        raise AuthError("Incorrect username or password.", 401)
    _clear_failures(username)
    return {"id": row["id"], "username": row["username"], "created_at": row["created_at"]}


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #


def issue_session(user_id: str) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    created = now()
    expires = created + timedelta(days=SESSION_DAYS)
    with get_db() as conn:
        # Opportunistic cleanup; keeps the table small without a scheduler.
        conn.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (iso(created),))
        conn.execute(
            "INSERT INTO auth_sessions (token_hash, user_id, created_at, expires_at, last_seen)"
            " VALUES (?, ?, ?, ?, ?)",
            (_session_hash(token), user_id, iso(created), iso(expires), iso(created)),
        )
    return token, expires


def user_for_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT u.id, u.username, u.created_at, s.expires_at"
            " FROM auth_sessions s JOIN auth_users u ON u.id = s.user_id"
            " WHERE s.token_hash = ? AND s.expires_at > ?",
            (_session_hash(token), iso(now())),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE auth_sessions SET last_seen = ? WHERE token_hash = ?",
            (iso(now()), _session_hash(token)),
        )
    return {"id": row["id"], "username": row["username"], "created_at": row["created_at"]}


def revoke_session(token: str | None) -> None:
    if not token:
        return
    with get_db() as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_session_hash(token),))


def ensure_bootstrap_user() -> None:
    """Optional CI/deployment bootstrap via environment variables.

    Normal installs start with the first-run setup screen; setting
    ``LIFEDESK_AUTH_PASSWORD`` (and optionally ``LIFEDESK_AUTH_USER``) creates
    the single owner account at startup. Passwords are still hashed.
    """
    password = os.environ.get("LIFEDESK_AUTH_PASSWORD", "")
    if not password or has_user():
        return
    username = os.environ.get("LIFEDESK_AUTH_USER", "owner").strip() or "owner"
    try:
        create_user(username, password)
    except AuthError:
        # A too-short bootstrap password must not crash startup; the setup
        # screen remains available and the problem is visible there.
        return
