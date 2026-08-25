"""Public profile routes (S14)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.dependencies.auth_provider import AuthenticatedCaller, get_optional_user
from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.services.auth_common import AuthError
from src.services.query_user_profile import get_user_profile

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.get("/{handle}")
def get_profile(
    handle: str,
    viewer: AuthenticatedCaller | None = Depends(get_optional_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return get_user_profile(session, handle, viewer.user if viewer else None)
    except AuthError as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
