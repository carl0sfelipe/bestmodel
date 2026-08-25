"""Run-claim listing with tallies and sort modes (S15).

Sorts:
- ``recent`` — newest first (default)
- ``controversial`` — smallest absolute margin first, ties by vote count
- ``strongest`` — largest absolute margin first
"""

from __future__ import annotations

from src.dependencies.database_session_provider import DatabaseSession
from src.services.claim_view import claim_view


def list_run_claims(
    session: DatabaseSession,
    status: str | None,
    sort: str,
    limit: int = 25,
    offset: int = 0,
) -> list[dict]:
    claims = session.list_run_claims(status, limit=200, offset=0)
    views = [claim_view(c, session.fetch_votes_for_claim(c["id"])) for c in claims]

    if sort == "controversial":
        views.sort(key=lambda v: (abs(v["tally"]["margin"]), -v["tally"]["voter_count"]))
    elif sort == "strongest":
        views.sort(key=lambda v: -abs(v["tally"]["margin"]))
    else:
        views.sort(key=lambda v: str(v.get("created_at")), reverse=True)

    return views[offset : offset + limit]
