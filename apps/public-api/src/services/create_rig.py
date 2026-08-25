"""Rig creation with deterministic slug generation (S14)."""

from __future__ import annotations

import re
import uuid

from src.dependencies.database_session_provider import DatabaseSession
from src.services.auth_common import AuthError, utcnow_iso
from src.services.rig_common import rig_view


def create_rig(session: DatabaseSession, caller: dict, payload: dict) -> dict:
    slug = payload.get("slug") or _slugify(payload["nickname"])
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,62}", slug):
        raise AuthError(400, "slug must match ^[a-z0-9][a-z0-9-]{2,62}$")
    if session.find_rig_by_slug(slug) is not None:
        raise AuthError(409, f"slug already taken: {slug}")

    now = utcnow_iso()
    record = {
        "id": str(uuid.uuid4()),
        "owner_id": caller["id"],
        "nickname": payload["nickname"],
        "slug": slug,
        "topology": payload.get("topology") or {},
        "is_public": payload.get("is_public", True),
        "hardware_submission_id": None,
        "created_at": now,
        "updated_at": now,
    }
    session.insert_rig(record)
    session.commit()
    return rig_view(record)


def _slugify(nickname: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", nickname.lower()).strip("-")
    return (slug or "rig")[:63]
