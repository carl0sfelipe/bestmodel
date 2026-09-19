"""S30: OAuth 2.0 authorization-code sign-in (GitHub, Hugging Face).

Deliberately dependency-free: the public-api makes no other outbound HTTP,
so the two calls per provider (token exchange + identity fetch) use stdlib
urllib instead of adding a client dependency. The network boundary lives in
thin wrappers (``_exchange_code`` / ``_fetch_identity``) so tests can
monkeypatch them, mirroring the passkey services.

Sessions issued here are the same 12h ``kind="session"`` tokens the passkey
flow issues — the console cannot tell the two apart, by design.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from src.services.auth_common import AuthError, expiry_iso, issue_token

STATE_TTL_SECONDS = 600
SESSION_TTL_SECONDS = 12 * 3600  # matches passkey sessions (S13)
HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")

PROVIDERS: dict[str, dict] = {
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": None,  # no scope = public profile only
        "client_id_env": "GITHUB_CLIENT_ID",
        "client_secret_env": "GITHUB_CLIENT_SECRET",
        "handle_suffix": "gh",
    },
    "huggingface": {
        "authorize_url": "https://huggingface.co/oauth/authorize",
        "token_url": "https://huggingface.co/oauth/token",
        "userinfo_url": "https://huggingface.co/oauth/userinfo",
        "scope": "openid profile",
        "client_id_env": "HUGGINGFACE_CLIENT_ID",
        "client_secret_env": "HUGGINGFACE_CLIENT_SECRET",
        "handle_suffix": "hf",
    },
}

# Where the browser may be sent back to with the token in the fragment.
# The fragment never reaches any server, but a closed list keeps begin
# links from being abused as open redirects.
ALLOWED_REDIRECT_URIS = (
    "https://www.bestmodel.run/console/index.html",
    "http://localhost:3000/console/index.html",
    "http://127.0.0.1:3000/console/index.html",
)

DEFAULT_PUBLIC_API_BASE = "https://api.bestmodel.run"


def provider_names() -> list[str]:
    return sorted(PROVIDERS)


def _credentials(provider: str) -> tuple[str, str]:
    config = PROVIDERS[provider]
    client_id = os.environ.get(config["client_id_env"], "").strip()
    client_secret = os.environ.get(config["client_secret_env"], "").strip()
    if not client_id or not client_secret:
        raise AuthError(503, f"oauth provider not configured: {provider}")
    return client_id, client_secret


def callback_url(provider: str) -> str:
    base = os.environ.get("PUBLIC_API_BASE", DEFAULT_PUBLIC_API_BASE).rstrip("/")
    return f"{base}/v1/auth/oauth/{provider}/callback"


# ---- state (CSRF + return destination) -------------------------------------
#
# The state carries everything the callback needs to know: when it was
# issued, for which provider, and WHERE the browser must land afterwards
# (an index into ALLOWED_REDIRECT_URIS). Providers redirect back with only
# code + state, so the return destination has to live inside the state
# itself, MAC'd against tampering.


def _state_secret() -> bytes:
    # Server-internal and stable across restarts; derived from the database
    # URL so no extra secret needs to be provisioned for this feature.
    seed = os.environ.get("DATABASE_URL", "") + "|oauth-state-v1"
    return hashlib.sha256(seed.encode()).digest()


def _state_mac(nonce: str, ts: str, provider: str, index: str) -> str:
    message = "\n".join((nonce, ts, provider, index)).encode()
    return hmac.new(_state_secret(), message, hashlib.sha256).hexdigest()


def sign_state(provider: str, redirect_uri: str) -> str:
    nonce = secrets.token_urlsafe(16)
    ts = str(int(time.time()))
    index = str(ALLOWED_REDIRECT_URIS.index(redirect_uri))
    return f"{ts}.{nonce}.{index}.{_state_mac(nonce, ts, provider, index)}"


def resolve_state(provider: str, state: str) -> str | None:
    """Return the redirect_uri baked into a valid, fresh state, else None."""
    parts = state.split(".")
    if len(parts) != 4:
        return None
    ts, nonce, index, mac = parts
    if not hmac.compare_digest(mac, _state_mac(nonce, ts, provider, index)):
        return None
    if not ts.isdigit() or not index.isdigit():
        return None
    if int(index) >= len(ALLOWED_REDIRECT_URIS):
        return None
    age = time.time() - int(ts)
    if not 0 <= age <= STATE_TTL_SECONDS:
        return None
    return ALLOWED_REDIRECT_URIS[int(index)]


# ---- outbound (monkeypatchable network boundary) ---------------------------


def _http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    bearer: str | None = None,
) -> dict:
    request = urllib.request.Request(url, method=method)
    request.add_header("Accept", "application/json")
    if bearer:
        request.add_header("Authorization", f"Bearer {bearer}")
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, body, timeout=10) as response:
        return json.loads(response.read().decode())


def _exchange_code(
    provider: str, code: str, client_id: str, client_secret: str
) -> str:
    config = PROVIDERS[provider]
    try:
        data = _http_json(
            config["token_url"],
            method="POST",
            payload={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": callback_url(provider),
            },
        )
    except (urllib.error.URLError, OSError) as exc:
        raise AuthError(502, f"could not reach {provider}: {exc}") from exc
    token = data.get("access_token")
    if not token:
        raise AuthError(401, f"{provider} did not return an access token")
    return token


def _fetch_identity(provider: str, access_token: str) -> dict:
    config = PROVIDERS[provider]
    try:
        data = _http_json(config["userinfo_url"], bearer=access_token)
    except (urllib.error.URLError, OSError) as exc:
        raise AuthError(502, f"could not reach {provider}: {exc}") from exc
    if provider == "github":
        account_id = data.get("id")
        login = data.get("login")
        display_name = data.get("name") or login
    else:
        account_id = data.get("sub")
        login = data.get("preferred_username")
        display_name = data.get("name") or login
    if account_id is None or not login:
        raise AuthError(401, f"{provider} returned an incomplete profile")
    return {
        "provider_account_id": str(account_id),
        "login": str(login),
        "display_name": str(display_name or login),
    }


# ---- handle resolution ------------------------------------------------------


def _normalize_login(login: str, provider_account_id: str) -> str:
    base = re.sub(r"[^a-z0-9_-]+", "-", login.lower())[:32].strip("-_")
    if not HANDLE_RE.match(base or ""):
        base = "user-" + provider_account_id[-8:].lower()
    return base


def _resolve_handle(
    session, provider: str, login: str, provider_account_id: str
) -> str:
    base = _normalize_login(login, provider_account_id)
    suffix = PROVIDERS[provider]["handle_suffix"]
    candidates = [base, f"{base[:29]}-{suffix}"]
    candidates += [f"{base[:29]}-{n}" for n in range(2, 10)]
    for candidate in candidates:
        if HANDLE_RE.match(candidate) and session.find_app_user_by_handle(candidate) is None:
            return candidate
    return "user-" + hashlib.sha256(provider_account_id.encode()).hexdigest()[:24]


# ---- orchestration ----------------------------------------------------------


def oauth_authorize_url(provider: str, redirect_uri: str) -> str:
    client_id, _ = _credentials(provider)
    config = PROVIDERS[provider]
    params = {
        "client_id": client_id,
        "redirect_uri": callback_url(provider),
        "state": sign_state(provider, redirect_uri),
    }
    if config["scope"]:
        params["scope"] = config["scope"]
    return f"{config['authorize_url']}?{urllib.parse.urlencode(params)}"


def oauth_login(session, provider: str, code: str, state: str) -> tuple[str, dict]:
    redirect_uri = resolve_state(provider, state)
    if redirect_uri is None:
        raise AuthError(400, "unknown or expired oauth state")
    client_id, client_secret = _credentials(provider)
    access_token = _exchange_code(provider, code, client_id, client_secret)
    identity = _fetch_identity(provider, access_token)

    account = session.find_oauth_account(provider, identity["provider_account_id"])
    if account is not None:
        user = session.find_app_user_by_id(account["app_user_id"])
        if user is None:
            raise AuthError(401, "oauth account points to a missing user")
        user_id = user["id"]
    else:
        user_id = str(uuid.uuid4())
        handle = _resolve_handle(
            session, provider, identity["login"], identity["provider_account_id"]
        )
        display_name = identity["display_name"][:64] or handle
        session.insert_app_user(
            {"id": user_id, "handle": handle, "display_name": display_name}
        )
        session.insert_oauth_account(
            {
                "id": str(uuid.uuid4()),
                "app_user_id": user_id,
                "provider": provider,
                "provider_account_id": identity["provider_account_id"],
                "login": identity["login"][:64],
                "display_name": display_name,
            }
        )

    record, plaintext = issue_token(
        session,
        user_id=user_id,
        kind="session",
        name=None,
        expires_at=expiry_iso(SESSION_TTL_SECONDS),
    )
    session.commit()
    return redirect_uri, {
        "access_token": plaintext,
        "token_type": "bearer",
        "expires_at": record["expires_at"],
    }
