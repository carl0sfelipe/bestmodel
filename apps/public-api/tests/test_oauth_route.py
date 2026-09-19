"""S30: OAuth sign-in routes (GitHub, Hugging Face)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from src.dependencies.database_session_provider import get_database_session
from src.main import create_app
from src.services import oauth_login

REDIRECT_URI = oauth_login.ALLOWED_REDIRECT_URIS[0]


@pytest.fixture
def client(database):
    app = create_app()
    app.dependency_overrides[get_database_session] = lambda: database
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def github_env(monkeypatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID", "gh-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "gh-client-secret")


@pytest.fixture
def hf_env(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_CLIENT_ID", "hf-client-id")
    monkeypatch.setenv("HUGGINGFACE_CLIENT_SECRET", "hf-client-secret")


def _identity(account_id="12345", login="octocat", name="Octo Cat"):
    return {
        "provider_account_id": account_id,
        "login": login,
        "display_name": name,
    }


def _mock_provider(monkeypatch, identity, token="provider-access-token"):
    monkeypatch.setattr(oauth_login, "_exchange_code", lambda *a, **k: token)
    monkeypatch.setattr(oauth_login, "_fetch_identity", lambda provider, access: identity)


def _begin(client, provider="github", redirect_uri=REDIRECT_URI):
    return client.get(
        "/v1/auth/oauth/{provider}/begin".format(provider=provider),
        params={"redirect_uri": redirect_uri},
    )


def _state_from(response) -> str:
    location = response.headers["location"]
    assert "state=" in location
    return location.split("state=")[1].split("&")[0]


# ---- begin -----------------------------------------------------------------


def test_begin_redirects_to_github(client, github_env):
    response = _begin(client)
    assert response.status_code == 307
    location = response.headers["location"]
    assert location.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=gh-client-id" in location
    assert "redirect_uri=https%3A%2F%2Fapi.bestmodel.run%2Fv1%2Fauth%2Foauth%2Fgithub%2Fcallback" in location
    assert "gh-client-secret" not in location


def test_begin_huggingface_requests_openid_scope(client, hf_env):
    response = _begin(client, provider="huggingface")
    assert response.status_code == 307
    location = response.headers["location"]
    assert location.startswith("https://huggingface.co/oauth/authorize?")
    assert "scope=openid+profile" in location


def test_begin_rejects_unknown_provider(client, github_env):
    assert _begin(client, provider="google").status_code == 404


def test_begin_rejects_foreign_redirect_uri(client, github_env):
    response = _begin(client, redirect_uri="https://evil.example/console")
    assert response.status_code == 400


def test_begin_unconfigured_provider_is_503(client, monkeypatch):
    monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
    assert _begin(client).status_code == 503


def test_begin_without_redirect_uri_defaults_to_production_console(client, github_env):
    response = client.get("/v1/auth/oauth/github/begin")
    assert response.status_code == 307
    assert response.headers["location"].startswith("https://github.com/login/oauth/authorize?")


# ---- callback --------------------------------------------------------------


def test_callback_issues_working_session_token(client, database, github_env, monkeypatch):
    _mock_provider(monkeypatch, _identity())
    state = _state_from(_begin(client))
    response = client.get(
        "/v1/auth/oauth/github/callback",
        params={"code": "abc", "state": state},
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith(REDIRECT_URI + "#")
    assert "auth_token=bm_" in location

    token = location.split("auth_token=")[1].split("&")[0]
    user = database.find_app_user_by_handle("octocat")
    assert user is not None
    listing = client.get(
        "/v1/auth/tokens", headers={"Authorization": f"Bearer {token}"}
    )
    assert listing.status_code == 200


def test_callback_huggingface_maps_oidc_fields(client, database, hf_env, monkeypatch):
    _mock_provider(
        monkeypatch,
        _identity(account_id="user_001", login="EnziIndustries", name="Enzi"),
    )
    state = _state_from(_begin(client, provider="huggingface"))
    response = client.get(
        "/v1/auth/oauth/huggingface/callback",
        params={"code": "abc", "state": state},
    )
    assert response.status_code == 303
    assert database.find_app_user_by_handle("enziindustries") is not None


def test_second_login_reuses_the_same_user(client, database, github_env, monkeypatch):
    _mock_provider(monkeypatch, _identity())
    state = _state_from(_begin(client))
    first = client.get(
        "/v1/auth/oauth/github/callback",
        params={"code": "abc", "state": state},
    )
    _mock_provider(monkeypatch, _identity())
    state = _state_from(_begin(client))
    second = client.get(
        "/v1/auth/oauth/github/callback",
        params={"code": "def", "state": state},
    )
    assert first.status_code == second.status_code == 303
    handles = [row["handle"] for row in database._users]
    assert handles.count("octocat") == 1


def test_handle_collision_gets_provider_suffix(client, database, github_env, monkeypatch):
    database.insert_app_user(
        {"id": "11111111-1111-1111-1111-111111111111", "handle": "octocat", "display_name": "Existing"}
    )
    _mock_provider(monkeypatch, _identity())
    state = _state_from(_begin(client))
    response = client.get(
        "/v1/auth/oauth/github/callback",
        params={"code": "abc", "state": state},
    )
    assert response.status_code == 303
    assert database.find_app_user_by_handle("octocat-gh") is not None


def test_bad_state_redirects_with_error(client, github_env, monkeypatch):
    _mock_provider(monkeypatch, _identity())
    response = client.get(
        "/v1/auth/oauth/github/callback",
        params={"code": "abc", "state": "garbage"},
    )
    assert response.status_code == 303
    assert "auth_error=" in response.headers["location"]


def test_state_is_provider_bound(client, github_env):
    state = oauth_login.sign_state("github", REDIRECT_URI)
    assert oauth_login.resolve_state("github", state) == REDIRECT_URI
    assert oauth_login.resolve_state("huggingface", state) is None


# --- S31: link a provider identity to the signed-in account -----------------

from src.services.auth_common import expiry_iso, issue_token  # noqa: E402


def _passkey_user(database, handle="carl0sfelipe", with_credential=True) -> tuple[str, str]:
    """A user that owns a passkey (or not) + a live session bearer."""
    user_id = f"user-{handle}"
    database.insert_app_user({"id": user_id, "handle": handle, "display_name": handle})
    if with_credential:
        database.insert_webauthn_credential(
            {
                "id": f"cred-{handle}",
                "app_user_id": user_id,
                "credential_id": handle.encode(),
                "public_key": b"cose",
                "sign_count": 0,
                "transports": [],
                "created_at": "2026-09-19T00:00:00Z",
                "last_used_at": None,
            }
        )
    _, bearer = issue_token(database, user_id=user_id, kind="session", name=None, expires_at=expiry_iso(3600))
    database.commit()
    return user_id, bearer


def _link_state(client, bearer, provider="github") -> str:
    started = client.post(
        f"/v1/auth/oauth/{provider}/link",
        json={"redirect_uri": REDIRECT_URI},
        headers={"Authorization": f"Bearer {bearer}"},
    )
    assert started.status_code == 200, started.text
    url = started.json()["authorize_url"]
    return url.split("state=")[1].split("&")[0]


def test_link_requires_session(client, github_env):
    assert client.post("/v1/auth/oauth/github/link").status_code == 401


def test_link_binds_new_identity_to_caller(client, database, github_env, monkeypatch):
    user_id, bearer = _passkey_user(database)
    _mock_provider(monkeypatch, _identity(account_id="777", login="carl0sfelipe"))
    state = _link_state(client, bearer)
    response = client.get("/v1/auth/oauth/github/callback", params={"code": "abc", "state": state})
    assert response.status_code == 303
    location = response.headers["location"]
    assert "linked=github" in location and "outcome=linked" in location
    assert "auth_token=" not in location  # link never issues a second session
    accounts = database.fetch_oauth_accounts_by_user(user_id)
    assert [a["provider_account_id"] for a in accounts] == ["777"]
    # no suffixed account was created
    assert database.find_app_user_by_handle("carl0sfelipe-gh") is None
    listing = client.get("/v1/auth/oauth/accounts", headers={"Authorization": f"Bearer {bearer}"}).json()
    assert listing == {"handle": "carl0sfelipe", "accounts": [{"provider": "github", "login": "carl0sfelipe", "display_name": "Octo Cat"}]}


def test_link_moves_identity_from_orphan_suffixed_account(client, database, github_env, monkeypatch):
    """The owner logged in with GitHub first (auto-created carl0sfelipe-gh),
    then registered a passkey on carl0sfelipe: linking moves the identity."""
    _mock_provider(monkeypatch, _identity(account_id="777", login="carl0sfelipe"))
    # first login auto-creates the -gh account (handle carl0sfelipe is taken below)
    user_id, bearer = _passkey_user(database)  # owns 'carl0sfelipe' with a passkey
    login = client.get("/v1/auth/oauth/github/callback", params={"code": "x", "state": _state_from(_begin(client))})
    assert login.status_code == 303
    orphan = database.find_app_user_by_handle("carl0sfelipe-gh")
    assert orphan is not None
    # now link from the passkey account
    state = _link_state(client, bearer)
    response = client.get("/v1/auth/oauth/github/callback", params={"code": "abc", "state": state})
    assert "outcome=moved" in response.headers["location"]
    assert [a["app_user_id"] for a in database.fetch_oauth_accounts_by_user(user_id)] == [user_id]
    assert database.fetch_oauth_accounts_by_user(orphan["id"]) == []


def test_link_refuses_identity_owned_by_account_with_passkey(client, database, github_env, monkeypatch):
    victim_id, _ = _passkey_user(database, handle="victim")
    database.insert_oauth_account(
        {"id": "oa-v", "app_user_id": victim_id, "provider": "github", "provider_account_id": "777", "login": "victim", "display_name": None}
    )
    _, bearer = _passkey_user(database, handle="attacker")
    _mock_provider(monkeypatch, _identity(account_id="777", login="victim"))
    state = _link_state(client, bearer)
    response = client.get("/v1/auth/oauth/github/callback", params={"code": "abc", "state": state})
    assert "link_error=" in response.headers["location"]
    assert database.fetch_oauth_accounts_by_user(victim_id)[0]["app_user_id"] == victim_id


def test_link_refuses_second_identity_of_same_provider(client, database, github_env, monkeypatch):
    user_id, bearer = _passkey_user(database)
    database.insert_oauth_account(
        {"id": "oa-1", "app_user_id": user_id, "provider": "github", "provider_account_id": "1", "login": "me", "display_name": None}
    )
    _mock_provider(monkeypatch, _identity(account_id="2", login="me-too"))
    state = _link_state(client, bearer)
    response = client.get("/v1/auth/oauth/github/callback", params={"code": "abc", "state": state})
    assert "link_error=" in response.headers["location"]
    assert len(database.fetch_oauth_accounts_by_user(user_id)) == 1


def test_link_state_cannot_be_retargeted():
    state = oauth_login.sign_state("github", REDIRECT_URI, link_user_id="user-a")
    ts, nonce, index, link, mac = state.split(".")
    forged = ".".join((ts, nonce, index, "user-b", mac))
    assert oauth_login.resolve_state_full("github", forged) is None
    assert oauth_login.resolve_state_full("github", state) == (REDIRECT_URI, "user-a")


def test_state_carries_its_own_destination():
    other = oauth_login.ALLOWED_REDIRECT_URIS[1]
    state = oauth_login.sign_state("github", other)
    assert oauth_login.resolve_state("github", state) == other


def test_expired_state_is_rejected():
    old_ts = str(int(time.time()) - oauth_login.STATE_TTL_SECONDS - 60)
    nonce = "abcdef"
    mac = oauth_login._state_mac(nonce, old_ts, "github", "1", "")
    assert oauth_login.resolve_state("github", f"{old_ts}.{nonce}.1..{mac}") is None


def test_github_style_callback_has_only_code_and_state(client, database, github_env, monkeypatch):
    """Regressão S30: o GitHub redireciona com só code+state — sem redirect_uri."""
    _mock_provider(monkeypatch, _identity())
    state = _state_from(_begin(client))
    response = client.get(
        "/v1/auth/oauth/github/callback",
        params={"code": "abc", "state": state},
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith(REDIRECT_URI + "#auth_token=bm_")
