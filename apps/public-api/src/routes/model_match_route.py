"""Model-to-hardware match route (plan flow 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.schemas.model_match_request import ModelMatchRequest
from src.services.query_model_match import query_model_configs

router = APIRouter(prefix="/v1/match", tags=["match"])


@router.post("/model-to-hardware")
def match_model_to_hardware(
    request: ModelMatchRequest,
    session: DatabaseSession = Depends(get_database_session),
) -> dict:
    return query_model_configs(session, request)
