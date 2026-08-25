"""Share-card routes (S18): SVG + markdown per claim."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.services.auth_common import AuthError
from src.services.render_claim_card import render_claim_card_markdown, render_claim_card_svg
from src.services.vote_on_claim import get_claim_with_tally

router = APIRouter(prefix="/v1/cards", tags=["cards"])


@router.get("/claims/{claim_id}.svg")
def claim_card_svg(
    claim_id: str,
    session: DatabaseSession = Depends(get_database_session),
) -> Response:
    try:
        view = get_claim_with_tally(session, claim_id)
    except AuthError as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    view["handle"] = _handle_for(session, view)
    svg = render_claim_card_svg(view)
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/claims/{claim_id}.md")
def claim_card_markdown(
    claim_id: str,
    session: DatabaseSession = Depends(get_database_session),
) -> Response:
    try:
        view = get_claim_with_tally(session, claim_id)
    except AuthError as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    view["handle"] = _handle_for(session, view)
    markdown = render_claim_card_markdown(view)
    return Response(content=markdown, media_type="text/markdown; charset=utf-8")


def _handle_for(session: DatabaseSession, view: dict) -> str | None:
    user = session.find_app_user_by_id(view.get("claimant_id"))
    return user["handle"] if user else None
