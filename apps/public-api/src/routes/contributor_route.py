"""Contributor registration route (Story 5.2).

Email-only lightweight account: the bearer token is shown once in the 201
response and only its sha256 is persisted. Used by the ``reported``
submission endpoint (``POST /v1/submissions/reported``).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.schemas.reported_submission_schema import ContributorRegistration
from src.services.submit_reported_run import ReportedRejected, register_contributor

router = APIRouter(prefix="/v1/contributors", tags=["contributors"])


@router.post("")
def register(registration: ContributorRegistration, session: DatabaseSession = Depends(get_database_session)) -> JSONResponse:
    try:
        status_code, body = register_contributor(session, registration)
    except ReportedRejected as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(status_code=status_code, content=body)
