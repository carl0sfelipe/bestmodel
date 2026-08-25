"""Benchmark submission routes: nonce issuance and multipart intake.

The submission endpoint reads ``multipart/form-data`` directly so that artifact
files named ``artifact_0``, ``artifact_1`` ... can be collected dynamically.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.dependencies.artifact_vault_provider import ArtifactVault, get_artifact_vault
from src.dependencies.auth_provider import AuthenticatedCaller, get_optional_user
from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.dependencies.redis_queue_provider import BenchmarkQueue, get_benchmark_queue
from src.schemas.benchmark_submission_schema import SubmissionForm
from src.services.submit_benchmark_run import SubmissionRejected, submit_benchmark_run

router = APIRouter(prefix="/v1/submissions", tags=["submissions"])


@router.get("/nonce")
def get_challenge_nonce() -> dict[str, str]:
    return {"challenge_nonce": str(uuid.uuid4())}


@router.post("")
async def submit_benchmark(
    request: Request,
    session: DatabaseSession = Depends(get_database_session),
    vault: ArtifactVault = Depends(get_artifact_vault),
    queue: BenchmarkQueue = Depends(get_benchmark_queue),
    caller: AuthenticatedCaller | None = Depends(get_optional_user),
) -> JSONResponse:
    form = await request.form()
    try:
        fields = _parse_fields(form)
        artifact_files = _extract_artifacts(form)
        status_code, body = submit_benchmark_run(
            session,
            vault,
            queue,
            fields,
            artifact_files,
            caller_user=caller.user if caller else None,
        )
    except SubmissionRejected as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(status_code=status_code, content=body)


def _parse_fields(form: Any) -> SubmissionForm:
    text_fields = {name: value for name, value in form.items() if isinstance(value, str)}
    try:
        return SubmissionForm(**text_fields)
    except ValidationError as exc:
        raise SubmissionRejected(400, f"invalid submission fields: {exc.errors()}") from exc


def _extract_artifacts(form: Any) -> list[Any]:
    artifacts = []
    index = 0
    while f"artifact_{index}" in form:
        artifacts.append(form[f"artifact_{index}"])
        index += 1
    return artifacts
