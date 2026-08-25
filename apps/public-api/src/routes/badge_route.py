"""Embeddable badge routes (S20)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.services.render_run_badge import render_run_badge

router = APIRouter(prefix="/v1/badges", tags=["badges"])


@router.get("/runs/{run_id}.svg")
def run_badge(
    run_id: str,
    session: DatabaseSession = Depends(get_database_session),
) -> Response:
    context = session.fetch_badge_context(run_id)
    if context is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "no validated run found for this badge"},
        )
    svg = render_run_badge(context)
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "max-age=300"})
