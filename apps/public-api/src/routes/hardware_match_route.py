"""Hardware-to-models match route (plan section 9.4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.schemas.hardware_match_request import HardwareMatchRequest
from src.services.query_hardware_match import query_hardware_matches

router = APIRouter(prefix="/v1/match", tags=["match"])


@router.post("/hardware-to-models")
def match_hardware_to_models(
    request: HardwareMatchRequest,
    session: DatabaseSession = Depends(get_database_session),
) -> dict:
    return query_hardware_matches(session, request)
