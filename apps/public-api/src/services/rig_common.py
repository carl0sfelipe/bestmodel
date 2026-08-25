"""Shared rig helpers (S14)."""

from __future__ import annotations

from src.dependencies.database_session_provider import DatabaseSession
from src.services.auth_common import AuthError


def rig_view(record: dict) -> dict:
    return {
        "id": record["id"],
        "owner_id": record["owner_id"],
        "nickname": record["nickname"],
        "slug": record["slug"],
        "topology": record.get("topology") or {},
        "is_public": record["is_public"],
        "hardware_submission_id": record.get("hardware_submission_id"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
    }


def require_owned_rig(session: DatabaseSession, caller: dict, slug: str) -> dict:
    rig = session.find_rig_by_slug(slug)
    if rig is None:
        raise AuthError(404, f"rig not found: {slug}")
    if rig["owner_id"] != caller["id"]:
        raise AuthError(403, "you do not own this rig")
    return rig
