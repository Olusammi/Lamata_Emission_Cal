"""backend/routers/auth.py — login / refresh / logout / me."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import TokenPair, TokenPayload, decode_token, get_current_user, issue_tokens, verify_login

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    username: str
    role: str


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest):
    role = verify_login(body.username, body.password)
    return issue_tokens(body.username, role)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest):
    payload = decode_token(body.refresh_token, expected_type="refresh")
    return issue_tokens(payload.sub, payload.role)


@router.post("/logout")
def logout():
    # Stateless JWTs: the client just discards its tokens. Nothing to
    # invalidate server-side without a token blacklist, which this app's
    # scale doesn't warrant yet.
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(user: TokenPayload = Depends(get_current_user)):
    return MeResponse(username=user.sub, role=user.role)
