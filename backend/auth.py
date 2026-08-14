"""
backend/auth.py — JWT auth with bcrypt-hashed passwords and login throttling.

Replaces app.py's check_password() (plaintext `==` against st.secrets,
no rate limiting, username-enumeration via distinct error messages) with:
  - bcrypt password verification (passlib)
  - short-lived JWT access tokens + longer-lived refresh tokens
  - per-username login lockout after repeated failures
  - a single generic error message for both "unknown user" and "wrong
    password", so the response can't be used to enumerate usernames
  - a `role` claim (admin | viewer) used to gate destructive endpoints
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from .config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

Role = Literal["admin", "viewer"]

# ── Login rate limiting (in-memory; fine at this app's scale — a single
# uvicorn worker fronting a small fleet-ops team, not a public login) ──
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60
_attempts: dict[str, list[float]] = {}


def _check_rate_limit(username: str) -> None:
    now = time.time()
    hits = [t for t in _attempts.get(username, []) if now - t < _LOCKOUT_SECONDS]
    _attempts[username] = hits
    if len(hits) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many login attempts. Try again in {_LOCKOUT_SECONDS} seconds.",
        )


def _record_failure(username: str) -> None:
    _attempts.setdefault(username, []).append(time.time())


def _clear_failures(username: str) -> None:
    _attempts.pop(username, None)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: Role
    type: Literal["access", "refresh"]
    exp: datetime


def _create_token(username: str, role: Role, kind: Literal["access", "refresh"], ttl: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": username, "role": role, "type": kind, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def issue_tokens(username: str, role: Role) -> TokenPair:
    settings = get_settings()
    access = _create_token(username, role, "access", timedelta(minutes=settings.access_token_ttl_minutes))
    refresh = _create_token(username, role, "refresh", timedelta(days=settings.refresh_token_ttl_days))
    return TokenPair(access_token=access, refresh_token=refresh)


def verify_login(username: str, password: str) -> Role:
    """Raises HTTPException(401) on any failure. Returns the user's role on success."""
    _check_rate_limit(username)
    settings = get_settings()
    user = next((u for u in settings.auth_users if u.get("username") == username), None)

    # Always run a bcrypt verify, even for unknown users, against a fixed
    # dummy hash — keeps the response time similar whether or not the
    # username exists, and the error message never distinguishes the two.
    dummy_hash = "$2b$12$C6UzMDM.H6dfI/f/IKcEeO0YEGQpTeSXt8QpNs6HJVFqM6Bqr8/Z."
    stored_hash = user["password_hash"] if user else dummy_hash
    ok = pwd_context.verify(password, stored_hash)

    if not user or not ok:
        _record_failure(username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password.")

    _clear_failures(username)
    return user.get("role", "viewer")


def decode_token(token: str, expected_type: Literal["access", "refresh"] = "access") -> TokenPayload:
    settings = get_settings()
    try:
        raw = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        data = TokenPayload(**raw)
    except (JWTError, ValueError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token.") from e
    if data.type != expected_type:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type.")
    return data


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> TokenPayload:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated.")
    return decode_token(creds.credentials, expected_type="access")


def require_admin(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required for this action.")
    return user
