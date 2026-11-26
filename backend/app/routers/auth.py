from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field, field_validator

from ..services.settings import set_display_name

from ..security import (
    COOKIE_NAME,
    COOKIE_SECURE,
    SESSION_DAYS,
    AuthError,
    authenticate,
    create_user,
    has_user,
    issue_session,
    revoke_session,
    user_for_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SetupRequest(BaseModel):
    username: str = Field(default="owner", min_length=1, max_length=64)
    display_name: str = Field(default="Ari Mensha", min_length=1, max_length=60)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("display_name")
    @classmethod
    def _clean_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Profile name cannot be empty")
        return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


def _status_payload(request: Request) -> dict:
    user = getattr(request.state, "user", None) or user_for_token(
        request.cookies.get(COOKIE_NAME)
    )
    return {
        "configured": has_user(),
        "authenticated": user is not None,
        "user": user,
        "session_days": SESSION_DAYS,
    }


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )


@router.get("/status")
def auth_status(request: Request):
    """Public handshake: tells the app whether setup or sign-in is required."""
    return _status_payload(request)


@router.post("/setup", status_code=201)
def setup(payload: SetupRequest, request: Request, response: Response):
    try:
        user = create_user(payload.username, payload.password)
        set_display_name(payload.display_name)
    except AuthError as exc:
        raise AuthError(str(exc), exc.status_code) from exc
    except ValueError as exc:
        raise AuthError(str(exc), 422) from exc
    token, _ = issue_session(user["id"])
    _set_cookie(response, token)
    request.state.user = user
    return _status_payload(request)


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response):
    user = authenticate(payload.username, payload.password)
    token, _ = issue_session(user["id"])
    _set_cookie(response, token)
    request.state.user = user
    return _status_payload(request)


@router.post("/logout")
def logout(request: Request, response: Response):
    revoke_session(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = getattr(request.state, "user", None) or user_for_token(
        request.cookies.get(COOKIE_NAME)
    )
    if user is None:
        raise AuthError("Authentication required.", 401)
    return {"user": user}
