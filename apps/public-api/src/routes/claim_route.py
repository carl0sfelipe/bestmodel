"""Run-claim routes (S15): create, browse, vote, retract."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.dependencies.auth_provider import (
    AuthenticatedCaller,
    get_current_user,
)
from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.schemas.claim_schemas import CLAIM_SORTS, ClaimVoteRequest, CreateRunClaimRequest
from src.services.auth_common import AuthError
from src.services.create_run_claim import create_run_claim
from src.services.query_run_claims import list_run_claims
from src.services.vote_on_claim import (
    get_claim_with_tally,
    retract_run_claim,
    vote_on_claim,
)

router = APIRouter(prefix="/v1/claims", tags=["claims"])


@router.post("")
def create(
    payload: CreateRunClaimRequest,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return create_run_claim(session, caller.user, payload.model_dump())
    except AuthError as exc:
        return _error(exc)


@router.get("")
def browse(
    status: str | None = Query(default=None),
    sort: str = Query(default="recent"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        if status is not None and status not in ("open", "settled_verified", "refuted", "retracted"):
            raise AuthError(400, f"invalid status filter: {status}")
        if sort not in CLAIM_SORTS:
            raise AuthError(400, f"sort must be one of {CLAIM_SORTS}")
        return list_run_claims(session, status, sort, limit, offset)
    except AuthError as exc:
        return _error(exc)


@router.get("/{claim_id}")
def get_claim(
    claim_id: str,
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return get_claim_with_tally(session, claim_id)
    except AuthError as exc:
        return _error(exc)


@router.post("/{claim_id}/votes")
def vote(
    claim_id: str,
    payload: ClaimVoteRequest,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return vote_on_claim(session, caller.user, claim_id, payload.verdict)
    except AuthError as exc:
        return _error(exc)


@router.post("/{claim_id}/retract")
def retract(
    claim_id: str,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return retract_run_claim(session, caller.user, claim_id)
    except AuthError as exc:
        return _error(exc)


def _error(exc: AuthError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
