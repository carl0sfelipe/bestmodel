"""Agent bearer-token management (S13).

Long-lived tokens for CLI/agent callers. The plaintext is returned exactly
once at creation; only the SHA-256 digest is persisted.
"""

from __future__ import annotations

from typing import Any

from src.services.auth_common import AuthError, issue_token


def create_agent_token(session, user: dict[str, Any], name: str) -> dict[str, Any]:
    record, plaintext = issue_token(
        session, user_id=user["id"], kind="agent", name=name, expires_at=None
    )
    session.commit()
    return {
        "id": record["id"],
        "name": name,
        "kind": "agent",
        "token": plaintext,
    }


def list_agent_tokens(session, user_id: str) -> list[dict[str, Any]]:
    return session.list_auth_tokens_for_user(user_id)


def revoke_agent_token(session, user_id: str, token_id: str) -> None:
    from src.services.auth_common import utcnow_iso

    affected = session.revoke_owned_auth_token(user_id, token_id, utcnow_iso())
    session.commit()
    if affected == 0:
        raise AuthError(404, "token not found or already revoked")
