"""Auth routes (S13): passkey ceremonies + agent token management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.dependencies.auth_provider import (
    AuthenticatedCaller,
    WebAuthnConfig,
    get_current_user,
    get_webauthn_config,
)
from src.dependencies.database_session_provider import DatabaseSession, get_database_session
from src.schemas.auth_schemas import (
    AgentTokenCreateRequest,
    PasskeyLoginOptionsRequest,
    PasskeyLoginVerifyRequest,
    PasskeyRegisterOptionsRequest,
    PasskeyRegisterVerifyRequest,
)
from src.services.authenticate_passkey import (
    passkey_login_options,
    verify_passkey_authentication,
)
from src.services.auth_common import AuthError
from src.services.manage_auth_tokens import (
    create_agent_token,
    list_agent_tokens,
    revoke_agent_token,
)
from src.services.register_passkey import (
    passkey_registration_options,
    verify_passkey_registration,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@router.post("/passkey/register/options")
def start_passkey_registration(
    payload: PasskeyRegisterOptionsRequest,
    session: DatabaseSession = Depends(get_database_session),
    config: WebAuthnConfig = Depends(get_webauthn_config),
) -> Any:
    try:
        return passkey_registration_options(session, config, payload.handle, payload.display_name)
    except AuthError as exc:
        return _error_response(exc)


@router.post("/passkey/register/verify")
def finish_passkey_registration(
    payload: PasskeyRegisterVerifyRequest,
    session: DatabaseSession = Depends(get_database_session),
    config: WebAuthnConfig = Depends(get_webauthn_config),
) -> Any:
    try:
        status_code, body = verify_passkey_registration(session, config, payload.handle, payload.credential)
    except AuthError as exc:
        return _error_response(exc)
    return JSONResponse(status_code=status_code, content=body)


@router.post("/passkey/login/options")
def start_passkey_login(
    payload: PasskeyLoginOptionsRequest,
    session: DatabaseSession = Depends(get_database_session),
    config: WebAuthnConfig = Depends(get_webauthn_config),
) -> Any:
    try:
        return passkey_login_options(session, config, payload.handle)
    except AuthError as exc:
        return _error_response(exc)


@router.post("/passkey/login/verify")
def finish_passkey_login(
    payload: PasskeyLoginVerifyRequest,
    session: DatabaseSession = Depends(get_database_session),
    config: WebAuthnConfig = Depends(get_webauthn_config),
) -> Any:
    try:
        return verify_passkey_authentication(session, config, payload.handle, payload.credential)
    except AuthError as exc:
        return _error_response(exc)


@router.post("/tokens")
def create_token(
    payload: AgentTokenCreateRequest,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    return create_agent_token(session, caller.user, payload.name)


@router.get("/tokens")
def list_tokens(
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    return list_agent_tokens(session, caller.user["id"])


@router.delete("/tokens/{token_id}")
def revoke_token(
    token_id: str,
    caller: AuthenticatedCaller = Depends(get_current_user),
    session: DatabaseSession = Depends(get_database_session),
) -> Any:
    try:
        revoke_agent_token(session, caller.user["id"], token_id)
    except AuthError as exc:
        return _error_response(exc)
    return {"revoked": True}
