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


# ---- callback --------------------------------------------------------------


def test_callback_issues_working_session_token(client, database, github_env, monkeypatch):
    _mock_provider(monkeypatch, _identity())
    state = _state_from(_begin(client))
    response = client.get(
        "/v1/auth/oauth/github/callback",
        params={"code": "abc", "state": state, "redirect_uri": REDIRECT_URI},
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
        params={"code": "abc", "state": state, "redirect_uri": REDIRECT_URI},
    )
    assert response.status_code == 303
    assert database.find_app_user_by_handle("enziindustries") is not None


def test_second_login_reuses_the_same_user(client, database, github_env, monkeypatch):
    _mock_provider(monkeypatch, _identity())
    state = _state_from(_begin(client))
    first = client.get(
        "/v1/auth/oauth/github/callback",
        params={"code": "abc", "state": state, "redirect_uri": REDIRECT_URI},
    )
    _mock_provider(monkeypatch, _identity())
    state = _state_from(_begin(client))
    second = client.get(
        "/v1/auth/oauth/github/callback",
        params={"code": "def", "state": state, "redirect_uri": REDIRECT_URI},
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
        params={"code": "abc", "state": state, "redirect_uri": REDIRECT_URI},
    )
    assert response.status_code == 303
    assert database.find_app_user_by_handle("octocat-gh") is not None


def test_bad_state_redirects_with_error(client, github_env, monkeypatch):
    _mock_provider(monkeypatch, _identity())
    response = client.get(
        "/v1/auth/oauth/github/callback",
        params={"code": "abc", "state": "garbage", "redirect_uri": REDIRECT_URI},
    )
    assert response.status_code == 303
    assert "auth_error=" in response.headers["location"]


def test_state_is_provider_bound(client, github_env):
    state = oauth_login.sign_state("github", REDIRECT_URI)
    assert oauth_login.verify_state("github", REDIRECT_URI, state)
    assert not oauth_login.verify_state("huggingface", REDIRECT_URI, state)


def test_expired_state_is_rejected():
    old_ts = str(int(time.time()) - oauth_login.STATE_TTL_SECONDS - 60)
    nonce = "abcdef"
    mac = oauth_login._state_mac(nonce, old_ts, "github", REDIRECT_URI)
    assert not oauth_login.verify_state("github", REDIRECT_URI, f"{old_ts}.{nonce}.{mac}")


def test_state_is_redirect_uri_bound():
    state = oauth_login.sign_state("github", REDIRECT_URI)
    assert not oauth_login.verify_state(
        "github", oauth_login.ALLOWED_REDIRECT_URIS[1], state
    )
