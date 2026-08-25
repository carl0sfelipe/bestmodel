"""S13 acceptance tests: passkey ceremonies, challenges and bearer tokens.

WebAuthn cryptography is delegated to the ``webauthn`` package; the tests
patch the thin wrapper functions in the service modules so the orchestration
(user creation, challenge lifecycle, credential storage, token issuance,
bearer authentication) is covered without a hardware authenticator.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.main import create_app
from src.services import authenticate_passkey, register_passkey

HANDLE = "ada"
OTHER_HANDLE = "grace"


@pytest.fixture()
def client(database):
    app = create_app()
    from src.dependencies.database_session_provider import get_database_session

    app.dependency_overrides[get_database_session] = lambda: database
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


class FakeOptions:
    def __init__(self, challenge: bytes):
        self.challenge = challenge


def _fake_b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _patch_registration(monkeypatch, challenge=b"reg-challenge"):
    monkeypatch.setattr(
        register_passkey,
        "_generate_registration_options",
        lambda config, user, excluded_credential_ids: FakeOptions(challenge),
    )
    monkeypatch.setattr(
        register_passkey,
        "_options_to_json",
        lambda options: '{"challenge": "%s"}' % _fake_b64(options.challenge),
    )

    def fake_verify(config, credential, expected_challenge):
        assert expected_challenge == challenge
        return SimpleNamespace(
            credential_id=b"\x01" * 32,
            credential_public_key=b"cose-pubkey",
            sign_count=0,
        )

    monkeypatch.setattr(register_passkey, "_verify_attestation", fake_verify)


def _patch_assertion(monkeypatch, challenge=b"login-challenge", new_sign_count=7):
    monkeypatch.setattr(
        authenticate_passkey,
        "_generate_authentication_options",
        lambda rp_id, allow_credentials: FakeOptions(challenge),
    )
    monkeypatch.setattr(
        authenticate_passkey,
        "_options_to_json",
        lambda options: '{"challenge": "%s"}' % _fake_b64(options.challenge),
    )

    def fake_verify(config, credential, expected_challenge, credential_public_key, credential_current_sign_count):
        assert credential_public_key == b"cose-pubkey"
        return SimpleNamespace(new_sign_count=new_sign_count)

    monkeypatch.setattr(authenticate_passkey, "_verify_assertion", fake_verify)


# --- registration -----------------------------------------------------------


def test_register_options_creates_user_and_stores_challenge(client, database):
    response = client.post(
        "/v1/auth/passkey/register/options",
        json={"handle": HANDLE, "display_name": "Ada L"},
    )
    assert response.status_code == 200
    body = response.json()
    user = database.find_app_user_by_handle(HANDLE)
    assert user is not None
    assert body["user_id"] == user["id"]
    assert body["options"]["challenge"]
    stored = database.fetch_auth_challenge(body["options"]["challenge"])
    assert stored is not None and stored["purpose"] == "registration"


def test_register_options_reuses_existing_handle(client, database):
    first = client.post("/v1/auth/passkey/register/options", json={"handle": HANDLE})
    second = client.post("/v1/auth/passkey/register/options", json={"handle": HANDLE})
    assert second.json()["user_id"] == first.json()["user_id"]
    handles = [u["handle"] for u in database._users if u["handle"] == HANDLE]
    assert len(handles) == 1


def test_register_options_rejects_bad_handle(client):
    response = client.post("/v1/auth/passkey/register/options", json={"handle": "-bad handle!"})
    assert response.status_code == 400


def test_register_verify_stores_credential_and_deletes_challenge(client, database, monkeypatch):
    _patch_registration(monkeypatch)
    options = client.post("/v1/auth/passkey/register/options", json={"handle": HANDLE}).json()
    credential = {
        "id": "cred-b64",
        "rawId": "cred-b64",
        "type": "public-key",
        "response": {"challenge": options["options"]["challenge"], "attestationObject": "x"},
    }
    response = client.post(
        "/v1/auth/passkey/register/verify",
        json={"handle": HANDLE, "credential": credential},
    )
    assert response.status_code == 201
    creds = database.fetch_webauthn_credentials_by_user(options["user_id"])
    assert len(creds) == 1 and bytes(creds[0]["public_key"]) == b"cose-pubkey"
    assert database.fetch_auth_challenge(options["options"]["challenge"]) is None


def test_register_verify_rejects_unknown_challenge(client, database, monkeypatch):
    _patch_registration(monkeypatch)
    client.post("/v1/auth/passkey/register/options", json={"handle": HANDLE})
    credential = {
        "id": "x", "rawId": "x", "type": "public-key",
        "response": {"challenge": "not-a-known-challenge"},
    }
    response = client.post("/v1/auth/passkey/register/verify", json={"handle": HANDLE, "credential": credential})
    assert response.status_code == 400


def test_register_verify_rejects_expired_challenge(client, database, monkeypatch):
    _patch_registration(monkeypatch)
    options = client.post("/v1/auth/passkey/register/options", json={"handle": HANDLE}).json()
    challenge = options["options"]["challenge"]
    database.expire_challenge(challenge)
    credential = {"id": "x", "rawId": "x", "type": "public-key", "response": {"challenge": challenge}}
    response = client.post("/v1/auth/passkey/register/verify", json={"handle": HANDLE, "credential": credential})
    assert response.status_code == 400


def test_register_verify_unknown_handle_404(client):
    credential = {"id": "x", "rawId": "x", "type": "public-key", "response": {"challenge": "c"}}
    response = client.post("/v1/auth/passkey/register/verify", json={"handle": "ghost", "credential": credential})
    assert response.status_code == 404


# --- login ------------------------------------------------------------------


def _register_passkey(client, database, monkeypatch, handle=HANDLE) -> str:
    _patch_registration(monkeypatch)
    options = client.post("/v1/auth/passkey/register/options", json={"handle": handle}).json()
    credential = {
        "id": "cred-" + handle,
        "rawId": "cred-" + handle,
        "type": "public-key",
        "response": {"challenge": options["options"]["challenge"], "attestationObject": "x"},
    }
    status = client.post("/v1/auth/passkey/register/verify", json={"handle": handle, "credential": credential})
    assert status.status_code == 201
    return options["user_id"]


def test_login_options_requires_known_handle_with_credentials(client, database, monkeypatch):
    assert client.post("/v1/auth/passkey/login/options", json={"handle": "ghost"}).status_code == 404

    _register_passkey(client, database, monkeypatch)
    response = client.post("/v1/auth/passkey/login/options", json={"handle": HANDLE})
    assert response.status_code == 200
    stored = database.fetch_auth_challenge(response.json()["options"]["challenge"])
    assert stored is not None and stored["purpose"] == "authentication"


def test_login_issues_working_session_token(client, database, monkeypatch):
    user_id = _register_passkey(client, database, monkeypatch)
    _patch_assertion(monkeypatch)
    options = client.post("/v1/auth/passkey/login/options", json={"handle": HANDLE}).json()

    credential = {
        "id": _fake_b64(b"\x01" * 32),
        "rawId": _fake_b64(b"\x01" * 32),
        "type": "public-key",
        "response": {
            "challenge": options["options"]["challenge"],
            "authenticatorData": "ad",
            "signature": "sig",
            "clientDataJSON": base64.urlsafe_b64encode(
                b'{"challenge":"%s"}' % options["options"]["challenge"].encode()
            ).rstrip(b"=").decode(),
        },
    }
    login = client.post("/v1/auth/passkey/login/verify", json={"handle": HANDLE, "credential": credential})
    assert login.status_code == 200
    token = login.json()["access_token"]

    # session counter was advanced
    stored_cred = database.fetch_webauthn_credentials_by_user(user_id)[0]
    assert stored_cred["sign_count"] == 7

    listing = client.get("/v1/auth/tokens", headers={"Authorization": f"Bearer {token}"})
    assert listing.status_code == 200
    assert isinstance(listing.json(), list)


def test_login_rejects_unregistered_credential_id(client, database, monkeypatch):
    _register_passkey(client, database, monkeypatch, OTHER_HANDLE)
    _patch_assertion(monkeypatch)
    options = client.post("/v1/auth/passkey/login/options", json={"handle": OTHER_HANDLE}).json()
    credential = {
        "id": "stranger-cred", "rawId": "stranger-cred", "type": "public-key",
        "response": {"challenge": options["options"]["challenge"]},
    }
    response = client.post(
        "/v1/auth/passkey/login/verify", json={"handle": OTHER_HANDLE, "credential": credential}
    )
    assert response.status_code == 400


# --- agent tokens -----------------------------------------------------------


def _login_token(client, database, monkeypatch) -> str:
    _register_passkey(client, database, monkeypatch)
    _patch_assertion(monkeypatch)
    options = client.post("/v1/auth/passkey/login/options", json={"handle": HANDLE}).json()
    credential = {
        "id": _fake_b64(b"\x01" * 32),
        "rawId": _fake_b64(b"\x01" * 32),
        "type": "public-key",
        "response": {"challenge": options["options"]["challenge"]},
    }
    login = client.post("/v1/auth/passkey/login/verify", json={"handle": HANDLE, "credential": credential})
    return login.json()["access_token"]


def test_create_list_and_use_agent_token(client, database, monkeypatch):
    session_token = _login_token(client, database, monkeypatch)
    headers = {"Authorization": f"Bearer {session_token}"}

    created = client.post("/v1/auth/tokens", json={"name": "ci-agent"}, headers=headers)
    assert created.status_code == 200
    agent_token = created.json()["token"]
    assert agent_token.startswith("bm_")
    # plaintext must not be retrievable afterwards
    assert all("token" not in row for row in client.get("/v1/auth/tokens", headers=headers).json())

    used = client.get("/v1/auth/tokens", headers={"Authorization": f"Bearer {agent_token}"})
    assert used.status_code == 200
    touched = [
        row for row in database._tokens if row["token_hash"] == hashlib.sha256(agent_token.encode()).hexdigest()
    ]
    assert touched[0]["last_used_at"] is not None


def test_revoked_token_is_rejected(client, database, monkeypatch):
    session_token = _login_token(client, database, monkeypatch)
    headers = {"Authorization": f"Bearer {session_token}"}
    created = client.post("/v1/auth/tokens", json={"name": "short-lived"}, headers=headers).json()

    revoked = client.delete(f"/v1/auth/tokens/{created['id']}", headers=headers)
    assert revoked.json() == {"revoked": True}

    denied = client.get("/v1/auth/tokens", headers={"Authorization": f"Bearer {created['token']}"})
    assert denied.status_code == 401


def test_cannot_revoke_other_users_token(client, database, monkeypatch):
    _login_token(client, database, monkeypatch)
    session_token = _login_token_for(client, database, monkeypatch, OTHER_HANDLE)
    headers = {"Authorization": f"Bearer {session_token}"}

    foreign_id = str(uuid.uuid4())
    response = client.delete(f"/v1/auth/tokens/{foreign_id}", headers=headers)
    assert response.status_code == 404


def test_expired_token_is_rejected(client, database, monkeypatch):
    session_token = _login_token(client, database, monkeypatch)
    expired = "bm_expiredtokenvalue0000000000000000000000"
    database.add_expired_token(
        {
            "id": str(uuid.uuid4()),
            "app_user_id": database.find_app_user_by_handle(HANDLE)["id"],
            "kind": "session",
            "token_hash": hashlib.sha256(expired.encode()).hexdigest(),
            "name": None,
            "expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "revoked_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used_at": None,
        }
    )
    response = client.get("/v1/auth/tokens", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_missing_and_garbage_tokens_are_rejected(client, database, monkeypatch):
    _login_token(client, database, monkeypatch)
    assert client.get("/v1/auth/tokens").status_code == 401
    assert client.get("/v1/auth/tokens", headers={"Authorization": "Bearer bm_nope"}).status_code == 401
    assert client.get("/v1/auth/tokens", headers={"Authorization": "Basic abc"}).status_code == 401


def _login_token_for(client, database, monkeypatch, handle: str) -> str:
    _register_passkey(client, database, monkeypatch, handle)
    _patch_assertion(monkeypatch, challenge=b"login-challenge-2")
    options = client.post("/v1/auth/passkey/login/options", json={"handle": handle}).json()
    credential = {
        "id": _fake_b64(b"\x01" * 32),
        "rawId": _fake_b64(b"\x01" * 32),
        "type": "public-key",
        "response": {"challenge": options["options"]["challenge"]},
    }
    login = client.post("/v1/auth/passkey/login/verify", json={"handle": handle, "credential": credential})
    return login.json()["access_token"]
