"""Follow graph management (S17)."""

from __future__ import annotations

import uuid

from src.dependencies.database_session_provider import DatabaseSession
from src.services.auth_common import AuthError, utcnow_iso


def follow_user(session: DatabaseSession, caller: dict, handle: str) -> dict:
    target = session.find_app_user_by_handle(handle.strip().lower())
    if target is None:
        raise AuthError(404, f"unknown handle: {handle}")
    if target["id"] == caller["id"]:
        raise AuthError(400, "cannot follow yourself")
    if session.is_following(caller["id"], target["id"]):
        raise AuthError(409, "already following this account")

    session.insert_follow(
        {
            "id": str(uuid.uuid4()),
            "follower_id": caller["id"],
            "followee_id": target["id"],
        }
    )
    session.insert_notification(
        {
            "id": str(uuid.uuid4()),
            "recipient_id": target["id"],
            "kind": "new_follower",
            "payload": {"follower_handle": caller["handle"]},
            "created_at": utcnow_iso(),
        }
    )
    session.commit()
    counts = session.fetch_follow_counts(target["id"])
    return {"is_following": True, "handle": target["handle"], **counts}


def unfollow_user(session: DatabaseSession, caller: dict, handle: str) -> dict:
    target = session.find_app_user_by_handle(handle.strip().lower())
    if target is None:
        raise AuthError(404, f"unknown handle: {handle}")
    removed = session.delete_follow(caller["id"], target["id"])
    session.commit()
    if removed == 0:
        raise AuthError(404, "not following this account")
    return {"is_following": False, "handle": target["handle"]}
