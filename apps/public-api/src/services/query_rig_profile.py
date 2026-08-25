"""Rig profile query: rig + its validated runs (S14)."""

from __future__ import annotations

from src.dependencies.database_session_provider import DatabaseSession
from src.services.auth_common import AuthError
from src.services.rig_common import rig_view


def get_rig_profile(
    session: DatabaseSession,
    slug: str,
    viewer: dict | None,
    run_limit: int = 20,
) -> dict:
    """Rig detail with validated runs; private rigs 404 for non-owners."""
    rig = session.find_rig_by_slug(slug)
    if rig is None or (not rig["is_public"] and (viewer or {}).get("id") != rig["owner_id"]):
        raise AuthError(404, f"rig not found: {slug}")

    runs = []
    if rig.get("hardware_submission_id"):
        runs = session.fetch_validated_runs_for_hardware(rig["hardware_submission_id"], run_limit)
    view = rig_view(rig)
    view["runs"] = runs
    return view
