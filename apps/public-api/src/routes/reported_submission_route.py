"""`reported` submission route (Story 5.2).

Multipart-free JSON intake for community numbers measured outside the signed
probe. Requires a contributor bearer token (401 otherwise), enforces the
per-IP quota (429), and stores the run with ``source_class='reported'`` /
``status='submitted'`` — out of the leaderboard until human review.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.schemas.reported_submission_schema import ReportedSubmissionBody
from src.services.submit_reported_run import (
    ReportedRejected,
    authenticate_contributor,
    submit_reported_run,
)

router = APIRouter(prefix="/v1/submissions/reported", tags=["submissions"])


@router.post("")
async def submit_reported(
    request: Request,
    session: DatabaseSession = Depends(get_database_session),
) -> JSONResponse:
    try:
        contributor = authenticate_contributor(session, request.headers.get("authorization"))
        body = _validate_body(await _parse_json_body(request))
        status_code, content = submit_reported_run(session, body, contributor, _client_ip(request))
    except ReportedRejected as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(status_code=status_code, content=content)


async def _parse_json_body(request: Request) -> dict:
    import json

    try:
        payload = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise ReportedRejected(400, f"body is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReportedRejected(400, "body must be a JSON object")
    return payload


def _validate_body(payload: dict) -> ReportedSubmissionBody:
    try:
        return ReportedSubmissionBody(**payload)
    except ValidationError as exc:
        raise ReportedRejected(400, f"invalid reported submission: {exc.errors()}") from exc


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
