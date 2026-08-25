"""Shared helpers for the S13 auth services."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone


class AuthError(Exception):
    """Raised for auth rejections carrying an HTTP status code."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return utcnow().isoformat()


def expiry_iso(seconds: int) -> str:
    return (utcnow() + timedelta(seconds=seconds)).isoformat()


HANDLE_PATTERN_ERROR = (
    "handle must match ^[a-z0-9][a-z0-9_-]{1,31}$ "
    "(lowercase letters, digits, '-', '_'; starts with letter/digit)"
)


def new_token_value() -> str:
    """Generate a bearer token plaintext; only its SHA-256 digest is stored."""
    return "bm_" + secrets.token_urlsafe(32)


def issue_token(
    session,
    *,
    user_id: str,
    kind: str,
    name: str | None,
    expires_at: str | None,
) -> tuple[dict, str]:
    """Persist an auth_token row and return (record, plaintext)."""
    import uuid

    from src.dependencies.auth_provider import hash_token

    plaintext = new_token_value()
    record = {
        "id": str(uuid.uuid4()),
        "app_user_id": user_id,
        "kind": kind,
        "token_hash": hash_token(plaintext),
        "name": name,
        "expires_at": expires_at,
        "created_at": utcnow_iso(),
        "last_used_at": None,
        "revoked_at": None,
    }
    session.insert_auth_token(record)
    return record, plaintext
