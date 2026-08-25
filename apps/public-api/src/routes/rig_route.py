"""Rig routes (S14): create, update, bind, and public profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from src.dependencies.auth_provider import (
    AuthenticatedCaller,
    get_current_user,
    get_optional_user,
)
from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.schemas.rig_schemas import BindRigRequest, CreateRigRequest, UpdateRigRequest
from src.services.auth_common import AuthError
from src.services.create_rig import create_rig
from src.services.query_rig_profile import get_rig_profile
from src.services.update_rig import bind_rig_to_hardware, update_rig

router = APIRouter(prefix="/v1/rigs", tags=["rigs"])


@router.post("")
def create(
    payload: CreateRigRequest,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return create_rig(session, caller.user, payload.model_dump())
    except AuthError as exc:
        return _error(exc)


@router.get("/{slug}")
def get_rig(
    slug: str,
    viewer: AuthenticatedCaller | None = Depends(get_optional_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return get_rig_profile(session, slug, viewer.user if viewer else None)
    except AuthError as exc:
        return _error(exc)


@router.patch("/{slug}")
def patch_rig(
    slug: str,
    payload: UpdateRigRequest,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return update_rig(session, caller.user, slug, payload.model_dump(exclude_unset=True))
    except AuthError as exc:
        return _error(exc)


@router.post("/{slug}/bind")
def bind_hardware(
    slug: str,
    payload: BindRigRequest,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return bind_rig_to_hardware(session, caller.user, slug, payload.hardware_submission_id)
    except AuthError as exc:
        return _error(exc)


def _error(exc: AuthError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
