"""WebAuthn relying-party configuration and bearer-token authentication.

``WebAuthnConfig`` is built from environment variables so the same image runs
against localhost during development and the public domain in production:

- ``AUTH_RP_ID`` (default ``localhost``)
- ``AUTH_RP_NAME`` (default ``bestmodel``)
- ``AUTH_EXPECTED_ORIGIN`` (default ``http://localhost:8000``)

``get_current_user`` resolves the ``Authorization: Bearer`` header against the
``auth_token`` table (SHA-256 digest lookup) and returns the owning user.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, Request

from src.dependencies.database_session_provider import DatabaseSession, get_database_session


@dataclass(frozen=True)
class WebAuthnConfig:
    rp_id: str
    rp_name: str
    expected_origin: str
    challenge_ttl_seconds: int = 120
    session_ttl_seconds: int = 12 * 3600

    @classmethod
    def from_env(cls) -> "WebAuthnConfig":
        return cls(
            rp_id=os.environ.get("AUTH_RP_ID", "localhost"),
            rp_name=os.environ.get("AUTH_RP_NAME", "bestmodel"),
            expected_origin=os.environ.get("AUTH_EXPECTED_ORIGIN", "http://localhost:8000"),
        )


def get_webauthn_config(request: Request) -> WebAuthnConfig:
    return request.app.state.auth_config


class AuthenticationRequired(HTTPException):
    def __init__(self, detail: str = "missing or invalid bearer token") -> None:
        super().__init__(status_code=401, detail=detail)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass()
class AuthenticatedCaller:
    user: dict[str, Any]
    token: dict[str, Any] = field(repr=False)


def get_current_user(
    authorization: str | None = Header(default=None),
    session: DatabaseSession = Depends(get_database_session),
) -> AuthenticatedCaller:
    """Resolve and validate the caller's bearer token; 401 on any failure."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationRequired()
    token = authorization[len("Bearer "):].strip()
    if not token:
        raise AuthenticationRequired()

    record = session.fetch_auth_token_by_hash(hash_token(token))
    if record is None:
        raise AuthenticationRequired()
    if record.get("revoked_at") is not None:
        raise AuthenticationRequired("token has been revoked")
    if record.get("expires_at") is not None:
        expires_at = _as_aware(record["expires_at"])
        if expires_at <= datetime.now(timezone.utc):
            raise AuthenticationRequired("token has expired")

    user = session.find_app_user_by_id(record["app_user_id"])
    if user is None:
        raise AuthenticationRequired()

    session.touch_auth_token_last_used(record["id"], _utcnow_iso())
    session.commit()
    return AuthenticatedCaller(user=user, token=record)


def _as_aware(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def get_optional_user(
    authorization: str | None = Header(default=None),
    session: DatabaseSession = Depends(get_database_session),
) -> AuthenticatedCaller | None:
    """Resolve the caller when a valid bearer token is present; else anonymous.

    Invalid or expired tokens degrade to anonymous instead of failing, so
    public views never break over stale client credentials.
    """
    try:
        return get_current_user(authorization=authorization, session=session)
    except HTTPException:
        return None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
