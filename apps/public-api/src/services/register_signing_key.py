"""S23: per-user signing keys — registration, listing, revocation.

A signing key is the cryptographic handle that ties submitted runs to a
user: the client keeps the Ed25519 PRIVATE key, the API stores only the
public PEM. Submissions carrying ``signature_key_id`` are verified against
the caller's OWN registered key (submit_benchmark_run enforces ownership).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.dependencies.auth_provider import AuthenticatedCaller
from src.dependencies.database_session_provider import DatabaseSession

ALGORITHM_ED25519 = "ed25519"


class SigningKeyError(ValueError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _validate_public_key_pem(public_key_pem: str) -> None:
    try:
        key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise SigningKeyError("public_key_pem is not a valid PEM key") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise SigningKeyError("only ed25519 public keys are accepted")


def register_signing_key(
    session: DatabaseSession, caller: AuthenticatedCaller, label: str, public_key_pem: str
) -> dict[str, Any]:
    label = label.strip()
    if not label:
        raise SigningKeyError("label is required")
    _validate_public_key_pem(public_key_pem)
    record = {
        "id": str(uuid.uuid4()),
        "app_user_id": caller.user["id"],
        "label": label,
        "public_key_pem": public_key_pem,
        "algorithm": ALGORITHM_ED25519,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "revoked_at": None,
    }
    session.insert_signing_key(record)
    session.commit()
    return _view(record, run_count=0)


def list_signing_keys(session: DatabaseSession, caller: AuthenticatedCaller) -> list[dict[str, Any]]:
    return [
        _view(row, run_count=int(row.get("run_count") or 0))
        for row in session.fetch_signing_keys_by_user(caller.user["id"])
    ]


def revoke_signing_key(
    session: DatabaseSession, caller: AuthenticatedCaller, key_id: str
) -> dict[str, Any]:
    record = session.fetch_signing_key_by_id(key_id)
    if record is None or record["app_user_id"] != caller.user["id"]:
        raise SigningKeyError("signing key not found", status_code=404)
    if record.get("revoked_at") is not None:
        raise SigningKeyError("signing key already revoked")
    session.revoke_signing_key(key_id, datetime.now(timezone.utc).isoformat())
    session.commit()
    record = session.fetch_signing_key_by_id(key_id) or record
    return _view(record, run_count=int(record.get("run_count") or 0))


def _view(record: dict[str, Any], run_count: int) -> dict[str, Any]:
    return {
        "id": record["id"],
        "label": record["label"],
        "algorithm": record["algorithm"],
        "created_at": record["created_at"],
        "revoked_at": record.get("revoked_at"),
        "run_count": run_count,
    }
