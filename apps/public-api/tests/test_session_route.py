"""BM-GOLIVE-1: the session endpoint the web front asks when it loads.

The front keeps its bearer token in localStorage, so the only way it can know
whether it is signed in — and as whom — is to ask the API. These tests pin the
contract: 401 without a token, the handle and tier with one.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.dependencies.database_session_provider import get_database_session
from src.main import create_app
from src.services import authenticate_passkey, register_passkey


@pytest.fixture
def client(database):
    app = create_app()
    app.dependency_overrides[get_database_session] = lambda: database
    return TestClient(app)


def _issue_token(client, handle="rigger"):
    import base64
    from types import SimpleNamespace

    monkey = pytest.MonkeyPatch()
    cred_id = b"\x01" * 32
    raw_id = base64.urlsafe_b64encode(cred_id).decode().rstrip("=")

    monkey.setattr(
        register_passkey, "_generate_registration_options",
        lambda *a, **k: SimpleNamespace(challenge=b"reg"),
    )
    monkey.setattr(
        register_passkey, "_options_to_json",
        lambda o: '{"challenge": "%s"}' % base64.urlsafe_b64encode(o.challenge).decode().rstrip("="),
    )
    monkey.setattr(
        register_passkey, "_verify_attestation",
        lambda *a, **k: SimpleNamespace(
            credential_id=cred_id, credential_public_key=b"pk", sign_count=0
        ),
    )
    monkey.setattr(
        authenticate_passkey, "_generate_authentication_options",
        lambda *a, **k: SimpleNamespace(challenge=b"login"),
    )
    monkey.setattr(
        authenticate_passkey, "_options_to_json",
        lambda o: '{"challenge": "%s"}' % base64.urlsafe_b64encode(o.challenge).decode().rstrip("="),
    )
    monkey.setattr(
        authenticate_passkey, "_verify_assertion",
        lambda *a, **k: SimpleNamespace(new_sign_count=3),
    )

    options = client.post("/v1/auth/passkey/register/options", json={"handle": handle}).json()
    client.post(
        "/v1/auth/passkey/register/verify",
        json={
            "handle": handle,
            "credential": {"response": {"challenge": options["options"]["challenge"]}},
        },
    )
    login_options = client.post("/v1/auth/passkey/login/options", json={"handle": handle}).json()
    login = client.post(
        "/v1/auth/passkey/login/verify",
        json={
            "handle": handle,
            "credential": {
                "rawId": raw_id,
                "response": {"challenge": login_options["options"]["challenge"]},
            },
        },
    )
    assert login.status_code == 200, login.text
    monkey.undo()
    return login.json()["access_token"]


def test_session_requires_a_token(client):
    assert client.get("/v1/auth/session").status_code == 401


def test_session_rejects_a_garbage_token(client):
    response = client.get(
        "/v1/auth/session", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_session_reports_the_handle_and_the_tier(client):
    token = _issue_token(client)
    response = client.get("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["handle"] == "rigger"
    # a fresh account starts at L0 with no points
    assert payload["reputation"]["tier"] == "L0"
    assert payload["reputation"]["points"] == 0
    assert payload["token_kind"] == "session"
