"""User profile query: identity + reputation + badges + visible rigs (S14).

This is the payload the profile page renders (S14 acceptance gate).
"""

from __future__ import annotations

from src.dependencies.database_session_provider import DatabaseSession
from src.services.auth_common import AuthError


def get_user_profile(
    session: DatabaseSession,
    handle: str,
    viewer: dict | None,
) -> dict:
    user = session.find_app_user_by_handle(handle.strip().lower())
    if user is None:
        raise AuthError(404, f"unknown handle: {handle}")

    reputation = session.fetch_reputation_by_user(user["id"]) or {
        "points": 0,
        "tier": "L0",
        "updated_at": None,
    }
    return {
        "handle": user["handle"],
        "display_name": user["display_name"],
        "created_at": user.get("created_at"),
        "reputation": {
            "points": reputation["points"],
            "tier": reputation["tier"],
            "updated_at": reputation.get("updated_at"),
        },
        "badges": session.fetch_badges_by_user(user["id"]),
        "rigs": [
            {
                "slug": rig["slug"],
                "nickname": rig["nickname"],
                "is_public": rig["is_public"],
                "hardware_submission_id": rig.get("hardware_submission_id"),
                "created_at": rig.get("created_at"),
            }
            for rig in session.list_visible_rigs_by_owner(user["id"], (viewer or {}).get("id"))
        ],
    }
