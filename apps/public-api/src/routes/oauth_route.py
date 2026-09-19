"""S30: OAuth sign-in routes (GitHub, Hugging Face).

Browser-flow routes: ``begin`` redirects to the provider, ``callback`` is
the provider's landing URL and always answers with a redirect back to the
console — the session token travels in the URL fragment, which browsers do
not send to any server. API-style errors (unknown provider, disallowed
redirect_uri) are the only JSON responses, since there is no trustworthy
place to redirect those to.
"""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, RedirectResponse

from src.dependencies.database_session_provider import (
    DatabaseSession,
    get_database_session,
)
from src.services import oauth_login
from src.services.auth_common import AuthError

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _json_error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


@router.get("/oauth/{provider}/begin", response_model=None)
def begin_oauth(
    provider: str,
    redirect_uri: str = Query(...),
    session: DatabaseSession = Depends(get_database_session),
) -> JSONResponse | RedirectResponse:
    if provider not in oauth_login.PROVIDERS:
        return _json_error(404, f"unknown oauth provider: {provider}")
    if redirect_uri not in oauth_login.ALLOWED_REDIRECT_URIS:
        return _json_error(400, "redirect_uri not allowed")
    try:
        url = oauth_login.oauth_authorize_url(provider, redirect_uri)
    except AuthError as exc:
        return _json_error(exc.status_code, exc.detail)
    return RedirectResponse(url, status_code=307)


@router.get("/oauth/{provider}/callback", response_model=None)
def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    redirect_uri: str = Query(...),
    session: DatabaseSession = Depends(get_database_session),
) -> JSONResponse | RedirectResponse:
    if provider not in oauth_login.PROVIDERS:
        return _json_error(404, f"unknown oauth provider: {provider}")
    if redirect_uri not in oauth_login.ALLOWED_REDIRECT_URIS:
        return _json_error(400, "redirect_uri not allowed")

    def redirect_with(**fragment: str) -> RedirectResponse:
        separator = "#" if "#" not in redirect_uri else "&"
        pair = urllib.parse.urlencode(fragment)
        return RedirectResponse(f"{redirect_uri}{separator}{pair}", status_code=303)

    try:
        result = oauth_login.oauth_login(session, provider, code, state, redirect_uri)
    except AuthError as exc:
        return redirect_with(auth_error=exc.detail)
    return redirect_with(
        auth_token=result["access_token"], expires_at=result["expires_at"]
    )
