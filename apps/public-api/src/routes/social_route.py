"""Social routes (S17): follow graph, notifications and the feed.

Registered BEFORE ``user_route`` so fixed segments (``/v1/feed``) never fall
into ``GET /v1/users/{handle}`` patterns.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.dependencies.auth_provider import (
    AuthenticatedCaller,
    get_current_user,
    get_optional_user,
)
from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.services.auth_common import AuthError
from src.services.build_feed import build_feed
from src.services.manage_follows import follow_user, unfollow_user

router = APIRouter(tags=["social"])


@router.post("/v1/users/{handle}/follow")
def follow(
    handle: str,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return follow_user(session, caller.user, handle)
    except AuthError as exc:
        return _error(exc)


@router.delete("/v1/users/{handle}/follow")
def unfollow(
    handle: str,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return unfollow_user(session, caller.user, handle)
    except AuthError as exc:
        return _error(exc)


@router.get("/v1/notifications")
def notifications(
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    return session.list_notifications_for_user(caller.user["id"])


@router.post("/v1/notifications/{notification_id}/read")
def mark_read(
    notification_id: str,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    affected = session.mark_notification_read(notification_id, caller.user["id"])
    session.commit()
    if affected == 0:
        return JSONResponse(status_code=404, content={"detail": "notification not found or already read"})
    return {"read": True}


@router.get("/v1/feed")
def feed(
    scope: str = Query(default="following"),
    sort: str = Query(default="recent"),
    limit: int = Query(default=30, ge=1, le=100),
    viewer: AuthenticatedCaller | None = Depends(get_optional_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    if scope not in ("following", "global"):
        return JSONResponse(status_code=400, content={"detail": "scope must be 'following' or 'global'"})
    if sort not in ("recent", "trending"):
        return JSONResponse(status_code=400, content={"detail": "sort must be 'recent' or 'trending'"})
    try:
        return build_feed(session, viewer.user if viewer else None, scope, sort, limit)
    except AuthError as exc:
        return _error(exc)


def _error(exc: AuthError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
