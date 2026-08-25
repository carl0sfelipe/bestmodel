"""Leaderboard route: validated runs with filtering and ranking."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.services.query_leaderboard import query_leaderboard

router = APIRouter(prefix="/v1", tags=["leaderboard"])


@router.get("/leaderboard")
def get_leaderboard(
    gpu_model_id: str | None = None,
    model_release_id: str | None = None,
    runtime_engine: str | None = None,
    quantization_profile_id: str | None = None,
    quant_format: str | None = None,
    context_tokens_min: int | None = None,
    context_tokens_max: int | None = None,
    batch_size: int | None = None,
    sort: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    session: DatabaseSession = Depends(get_database_session),
) -> dict:
    filters = {
        "gpu_model_id": gpu_model_id,
        "model_release_id": model_release_id,
        "runtime_engine": runtime_engine,
        "quantization_profile_id": quantization_profile_id,
        "quant_format": quant_format,
        "context_tokens_min": context_tokens_min,
        "context_tokens_max": context_tokens_max,
        "batch_size": batch_size,
    }
    return query_leaderboard(session, filters, sort, limit, offset)
