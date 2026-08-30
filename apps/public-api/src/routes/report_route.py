"""Run-report routes (S28): denúncia de run irreal + moderação."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.dependencies.auth_provider import (
    AuthenticatedCaller,
    get_current_user,
)
from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.services.auth_common import AuthError
from src.services.create_run_report import confirm_report, create_run_report, dismiss_report

router = APIRouter(prefix="/v1", tags=["reports"])


class CreateRunReportRequest(BaseModel):
    reason_category: str
    reason_detail: str | None = None


@router.post("/run-claims/{claim_id}/reports")
def report_claim(
    claim_id: str,
    payload: CreateRunReportRequest,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return create_run_report(
            session, caller.user, "run_claim", claim_id, payload.model_dump()
        )
    except AuthError as exc:
        return _error(exc)


@router.post("/runs/{run_id}/reports")
def report_run(
    run_id: str,
    payload: CreateRunReportRequest,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return create_run_report(
            session, caller.user, "benchmark_run", run_id, payload.model_dump()
        )
    except AuthError as exc:
        return _error(exc)


@router.get("/reports")
def browse_reports(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        from src.services.create_run_report import require_moderator

        require_moderator(caller.user)
        if status is not None and status not in ("open", "confirmed", "dismissed"):
            raise AuthError(400, f"invalid status filter: {status}")
        return {"reports": session.list_run_reports(status, limit)}
    except AuthError as exc:
        return _error(exc)


@router.post("/reports/{report_id}/confirm")
def confirm(
    report_id: str,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return confirm_report(session, caller.user, report_id)
    except AuthError as exc:
        return _error(exc)


@router.post("/reports/{report_id}/dismiss")
def dismiss(
    report_id: str,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return dismiss_report(session, caller.user, report_id)
    except AuthError as exc:
        return _error(exc)


def _error(exc: AuthError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
