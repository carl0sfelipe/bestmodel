"""Rig mutation: field updates and hardware binding (S14)."""

from __future__ import annotations

from src.dependencies.database_session_provider import DatabaseSession
from src.services.auth_common import AuthError
from src.services.rig_common import require_owned_rig, rig_view


def update_rig(session: DatabaseSession, caller: dict, slug: str, fields: dict) -> dict:
    rig = require_owned_rig(session, caller, slug)
    payload = {k: v for k, v in fields.items() if v is not None}
    if payload:
        affected = session.update_rig(rig["id"], payload)
        session.commit()
        if affected == 0:
            raise AuthError(404, f"rig not found: {slug}")
    return rig_view(session.find_rig_by_slug(slug))


def bind_rig_to_hardware(
    session: DatabaseSession, caller: dict, slug: str, hardware_submission_id: str
) -> dict:
    rig = require_owned_rig(session, caller, slug)
    submission = session.find_hardware_submission(hardware_submission_id)
    if submission is None:
        raise AuthError(404, f"hardware submission not found: {hardware_submission_id}")
    session.update_rig(rig["id"], {"hardware_submission_id": hardware_submission_id})
    session.commit()
    return rig_view(session.find_rig_by_slug(slug))
