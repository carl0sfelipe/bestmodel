"""S14 acceptance tests: rigs, catalog binding and user profiles.

Covers the L02 gate "profile page renders from API fixtures": the profile
payload is asserted end-to-end from fake-adapter fixtures, including
reputation, badges and visibility-filtered rigs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.main import create_app


@pytest.fixture()
def client(database):
    app = create_app()
    from fastapi.testclient import TestClient
    from src.dependencies.database_session_provider import get_database_session

    app.dependency_overrides[get_database_session] = lambda: database
    with TestClient(app) as test_client:
        yield test_client


def _passkey_session(client, database, monkeypatch, handle: str) -> str:
    """Drive the S13 ceremonies with patched WebAuthn to get a bearer token."""
    import base64
    from types import SimpleNamespace

    from src.services import authenticate_passkey, register_passkey

    fake_credential_id = b"\x01" * 32
    fake_credential_raw_id = base64.urlsafe_b64encode(fake_credential_id).decode().rstrip("=")

    def fake_reg_options(*args, **kwargs):
        return SimpleNamespace(challenge=b"reg-challenge")

    def fake_opt_json(options):
        import base64

        return '{"challenge": "%s"}' % base64.urlsafe_b64encode(options.challenge).decode().rstrip("=")

    def fake_attest(*args, **kwargs):
        return SimpleNamespace(credential_id=fake_credential_id, credential_public_key=b"pk", sign_count=0)

    def fake_assert_options(*args, **kwargs):
        return SimpleNamespace(challenge=b"login-challenge")

    def fake_assert(*args, **kwargs):
        return SimpleNamespace(new_sign_count=1)

    monkeypatch.setattr(register_passkey, "_generate_registration_options", fake_reg_options)
    monkeypatch.setattr(register_passkey, "_options_to_json", fake_opt_json)
    monkeypatch.setattr(register_passkey, "_verify_attestation", fake_attest)
    monkeypatch.setattr(authenticate_passkey, "_generate_authentication_options", fake_assert_options)
    monkeypatch.setattr(authenticate_passkey, "_options_to_json", fake_opt_json)
    monkeypatch.setattr(authenticate_passkey, "_verify_assertion", fake_assert)

    options = client.post("/v1/auth/passkey/register/options", json={"handle": handle}).json()
    client.post(
        "/v1/auth/passkey/register/verify",
        json={"handle": handle, "credential": {"response": {"challenge": options["options"]["challenge"]}}},
    )
    login_options = client.post("/v1/auth/passkey/login/options", json={"handle": handle}).json()
    login = client.post(
        "/v1/auth/passkey/login/verify",
        json={"handle": handle, "credential": {"rawId": fake_credential_raw_id, "response": {"challenge": login_options["options"]["challenge"]}}},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


# --- creation ----------------------------------------------------------------


def test_create_rig_requires_auth(client):
    response = client.post("/v1/rigs", json={"nickname": "Battlestation"})
    assert response.status_code == 401


def test_create_rig_generates_slug(client, database, monkeypatch):
    token = _passkey_session(client, database, monkeypatch, "ada")
    response = client.post(
        "/v1/rigs",
        json={"nickname": "Battle Station 3090!", "topology": {"gpu": "RTX 3090"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["slug"] == "battle-station-3090"
    assert body["topology"] == {"gpu": "RTX 3090"}
    assert body["is_public"] is True


def test_create_rig_duplicate_slug_conflicts(client, database, monkeypatch):
    token = _passkey_session(client, database, monkeypatch, "ada")
    payload = {"nickname": "Rig", "slug": "my-rig"}
    first = client.post("/v1/rigs", json=payload, headers={"Authorization": f"Bearer {token}"})
    second = client.post("/v1/rigs", json={"nickname": "Other"}, headers={"Authorization": f"Bearer {token}"})
    conflict = client.post(
        "/v1/rigs", json={"nickname": "Whatever", "slug": "my-rig"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert first.status_code == 200 and second.status_code == 200
    assert conflict.status_code == 409


def test_create_rig_rejects_invalid_explicit_slug(client, database, monkeypatch):
    token = _passkey_session(client, database, monkeypatch, "ada")
    response = client.post(
        "/v1/rigs", json={"nickname": "Rig", "slug": "-bad_slug_"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422  # schema pattern


# --- visibility --------------------------------------------------------------


def _make_rig(client, database, monkeypatch, handle: str, slug: str, is_public: bool) -> str:
    token = _passkey_session(client, database, monkeypatch, handle)
    created = client.post(
        "/v1/rigs",
        json={"nickname": slug, "slug": slug, "is_public": is_public},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 200
    return token


def test_private_rig_hidden_from_others_and_anonymous(client, database, monkeypatch):
    owner_token = _make_rig(client, database, monkeypatch, "ada", "secret-rig", is_public=False)
    _passkey_session(client, database, monkeypatch, "grace")

    anonymous = client.get("/v1/rigs/secret-rig")
    stranger = client.get("/v1/rigs/secret-rig", headers={"Authorization": "Bearer bm_garbage"})
    owner_view = client.get("/v1/rigs/secret-rig", headers={"Authorization": f"Bearer {owner_token}"})

    assert anonymous.status_code == 404
    assert stranger.status_code == 404  # stale tokens degrade to anonymous
    assert owner_view.status_code == 200
    assert owner_view.json()["is_public"] is False


def test_public_rig_visible_to_everyone(client, database, monkeypatch):
    _make_rig(client, database, monkeypatch, "ada", "loud-rig", is_public=True)
    assert client.get("/v1/rigs/loud-rig").status_code == 200


# --- update + binding --------------------------------------------------------


def _seed_hardware_submission(database, hardware_id: str) -> None:
    database.insert_hardware_submission(
        {
            "id": hardware_id,
            "owner_account_id": "00000000-0000-0000-0000-000000000099",
            "gpu_model_id": "gpu-rtx-4090",
            "cpu_model_id": None,
            "gpu_count": 1,
            "ram_gib": 64,
            "os_name": "Linux",
            "os_version": "6.9",
            "environment_snapshot": {},
        }
    )


def test_update_rig_only_by_owner(client, database, monkeypatch):
    _make_rig(client, database, monkeypatch, "ada", "ada-rig", True)
    other_token = _passkey_session(client, database, monkeypatch, "grace")

    forbidden = client.patch(
        "/v1/rigs/ada-rig", json={"nickname": "hijacked"}, headers={"Authorization": f"Bearer {other_token}"}
    )
    assert forbidden.status_code == 403


def test_bind_unknown_submission_404(client, database, monkeypatch):
    token = _make_rig(client, database, monkeypatch, "ada", "ada-rig", True)
    response = client.post(
        "/v1/rigs/ada-rig/bind",
        json={"hardware_submission_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_bound_rig_profile_shows_validated_runs(client, database, monkeypatch):
    token = _make_rig(client, database, monkeypatch, "ada", "ada-rig", True)
    hardware_id = "00000000-0000-0000-0000-000000000010"  # seeded run hw id in FakeDatabase
    _seed_hardware_submission(database, hardware_id)

    bound = client.post(
        "/v1/rigs/ada-rig/bind",
        json={"hardware_submission_id": hardware_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bound.status_code == 200
    assert bound.json()["hardware_submission_id"] == hardware_id

    profile = client.get("/v1/rigs/ada-rig").json()
    assert len(profile["runs"]) >= 1
    run = profile["runs"][0]
    assert run["model_release_id"].startswith("model-")
    assert run["run_id"]


def test_unbound_rig_profile_has_empty_runs(client, database, monkeypatch):
    _make_rig(client, database, monkeypatch, "ada", "fresh-rig", True)
    profile = client.get("/v1/rigs/fresh-rig").json()
    assert profile["runs"] == []


# --- user profile (S14 acceptance: renders from API fixtures) ----------------


def _award_fixtures(database, handle: str) -> str:
    user = database.find_app_user_by_handle(handle)
    database._reputations[database._reputations.index(
        next(r for r in database._reputations if r["app_user_id"] == user["id"])
    )] = {
        "app_user_id": user["id"],
        "points": 340,
        "tier": "L2",
        "updated_at": datetime.now(timezone.utc),
    }
    database.insert_badge({"id": str(uuid.uuid4()), "app_user_id": user["id"], "code": "first_verified_run"})
    return user["id"]


def test_user_profile_renders_full_payload(client, database, monkeypatch):
    _make_rig(client, database, monkeypatch, "ada", "public-rig", True)
    _make_rig(client, database, monkeypatch, "ada", "hidden-rig", False)
    _award_fixtures(database, "ada")

    response = client.get("/v1/users/ada")
    assert response.status_code == 200
    body = response.json()

    assert body["handle"] == "ada"
    assert body["reputation"]["points"] == 340
    assert body["reputation"]["tier"] == "L2"
    assert [b["code"] for b in body["badges"]] == ["first_verified_run"]
    slugs = [r["slug"] for r in body["rigs"]]
    assert "public-rig" in slugs and "hidden-rig" not in slugs  # anonymous viewer


def test_user_profile_owner_sees_private_rigs(client, database, monkeypatch):
    _make_rig(client, database, monkeypatch, "ada", "public-rig", True)
    _make_rig(client, database, monkeypatch, "ada", "hidden-rig", False)
    token = _passkey_session(client, database, monkeypatch, "ada")  # fresh session, same user

    body = client.get("/v1/users/ada", headers={"Authorization": f"Bearer {token}"}).json()
    slugs = [r["slug"] for r in body["rigs"]]
    assert slugs == ["public-rig", "hidden-rig"]


def test_unknown_user_profile_404(client):
    assert client.get("/v1/users/ghost").status_code == 404
