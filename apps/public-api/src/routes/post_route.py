"""L08: the classic social layer — posts, comments, likes.

Reads are public. Writes need a bearer token (passkey or OAuth session, or an
agent token). Every route answers with the API's own `detail` on failure — no
invented messages.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from src.dependencies.auth_provider import (
    AuthenticatedCaller,
    get_current_user,
    get_optional_user,
)
from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.services.auth_common import AuthError
from src.services.social_posts import (
    add_comment,
    create_post,
    delete_post,
    get_post,
    toggle_comment_like,
    toggle_post_like,
)

router = APIRouter(prefix="/v1", tags=["social-posts"])


class CreatePostRequest(BaseModel):
    # extra="allow" on purpose: a body carrying numbers must reach the
    # service so it can refuse it in words, not be silently dropped by the
    # schema and accepted as a plain note.
    model_config = ConfigDict(extra="allow")

    body: str = Field(min_length=1, max_length=2000)
    kind: str | None = Field(default=None, max_length=16)
    claim_id: str | None = Field(default=None, max_length=64)
    rig_slug: str | None = Field(default=None, max_length=128)
    model_release_id: str | None = Field(default=None, max_length=128)


class CreateCommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=1000)
    parent_id: str | None = Field(default=None, max_length=64)


@router.post("/posts")
def post_create(
    payload: CreatePostRequest,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return create_post(session, caller.user, payload.model_dump())
    except AuthError as exc:
        return _error(exc)


@router.get("/posts/{post_id}")
def post_read(
    post_id: str,
    viewer: AuthenticatedCaller | None = Depends(get_optional_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return get_post(session, post_id, viewer.user if viewer else None)
    except AuthError as exc:
        return _error(exc)


@router.delete("/posts/{post_id}")
def post_delete(
    post_id: str,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return delete_post(session, caller.user, post_id)
    except AuthError as exc:
        return _error(exc)


@router.post("/posts/{post_id}/comments")
def comment_create(
    post_id: str,
    payload: CreateCommentRequest,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return add_comment(
            session, caller.user, post_id, payload.body, payload.parent_id
        )
    except AuthError as exc:
        return _error(exc)


@router.post("/posts/{post_id}/likes")
def post_like(
    post_id: str,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return toggle_post_like(session, caller.user, post_id)
    except AuthError as exc:
        return _error(exc)


@router.post("/comments/{comment_id}/likes")
def comment_like(
    comment_id: str,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        return toggle_comment_like(session, caller.user, comment_id)
    except AuthError as exc:
        return _error(exc)


def _error(exc: AuthError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
