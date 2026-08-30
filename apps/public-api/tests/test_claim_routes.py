"""S15 route tests: claim creation (frozen priors), voting, listing, retract."""

from __future__ import annotations

import uuid

import pytest

from src.main import create_app

HANDLE_A = "ada"
HANDLE_B = "grace"


@pytest.fixture()
def client(database):
    app = create_app()
    from fastapi.testclient import TestClient
    from src.dependencies.database_session_provider import get_database_session

    app.dependency_overrides[get_database_session] = lambda: database
    with TestClient(app) as test_client:
        yield test_client


def _session_token(client, database, monkeypatch, handle: str) -> str:
    """Reuse the S13/S14 patched-ceremony helper pattern for a bearer token."""
    import base64
    from types import SimpleNamespace

    from src.services import authenticate_passkey, register_passkey

    cred_id = b"\x01" * 32
    raw_id = base64.urlsafe_b64encode(cred_id).decode().rstrip("=")

    monkeypatch.setattr(
        register_passkey, "_generate_registration_options",
        lambda *a, **k: SimpleNamespace(challenge=b"reg"),
    )
    monkeypatch.setattr(
        register_passkey, "_options_to_json",
        lambda o: '{"challenge": "%s"}' % base64.urlsafe_b64encode(o.challenge).decode().rstrip("="),
    )
    monkeypatch.setattr(
        register_passkey, "_verify_attestation",
        lambda *a, **k: SimpleNamespace(credential_id=cred_id, credential_public_key=b"pk", sign_count=0),
    )
    monkeypatch.setattr(
        authenticate_passkey, "_generate_authentication_options",
        lambda *a, **k: SimpleNamespace(challenge=b"login"),
    )
    monkeypatch.setattr(
        authenticate_passkey, "_options_to_json",
        lambda o: '{"challenge": "%s"}' % base64.urlsafe_b64encode(o.challenge).decode().rstrip("="),
    )
    monkeypatch.setattr(
        authenticate_passkey, "_verify_assertion",
        lambda *a, **k: SimpleNamespace(new_sign_count=3),
    )

    options = client.post("/v1/auth/passkey/register/options", json={"handle": handle}).json()
    client.post(
        "/v1/auth/passkey/register/verify",
        json={"handle": handle, "credential": {"response": {"challenge": options["options"]["challenge"]}}},
    )
    login_options = client.post("/v1/auth/passkey/login/options", json={"handle": handle}).json()
    login = client.post(
        "/v1/auth/passkey/login/verify",
        json={"handle": handle, "credential": {"rawId": raw_id, "response": {"challenge": login_options["options"]["challenge"]}}},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _claim_payload(**overrides):
    payload = {
        "model_release_id": "model-qwen25-coder-7b",  # seeded in FakeDatabase
        "claimed_metrics": {"decode_tok_s": 41.5},
        "note": "felt fast on my box",
    }
    payload.update(overrides)
    return payload


# --- creation ----------------------------------------------------------------


def test_create_claim_requires_auth(client):
    assert client.post("/v1/claims", json=_claim_payload()).status_code == 401


def test_create_claim_freezes_pool_prior(client, database, monkeypatch):
    token = _session_token(client, database, monkeypatch, HANDLE_A)
    response = client.post("/v1/claims", json=_claim_payload(), headers=_auth(token))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "open"
    prior = body["prior_snapshot"]
    assert prior["computed_at"]
    # seeded fake pool has validated runs for this model → measured prior exists
    assert prior["pool"] is not None
    assert prior["pool"]["run_count"] >= 1
    assert prior["pool"]["basis"] == "measured"


def test_prior_is_frozen_when_predictors_improve(client, database, monkeypatch):
    token = _session_token(client, database, monkeypatch, HANDLE_A)
    created = client.post("/v1/claims", json=_claim_payload(), headers=_auth(token)).json()
    claim_id = created["id"]

    # simulate predictor improvement by mutating the live pool data
    database._metrics.append(
        {
            "benchmark_run_id": database._runs[-1]["id"],
            "kind": "decode_tok_s",
            "p50_value": 99999.0,
            "unit": "tok/s",
        }
    )
    fetched = client.get(f"/v1/claims/{claim_id}").json()
    assert fetched["prior_snapshot"] == created["prior_snapshot"]


def test_claim_with_roofline_prior_from_gpu(client, database, monkeypatch):
    token = _session_token(client, database, monkeypatch, HANDLE_A)
    gpus = database.fetch_all_gpus()
    gpu_id = next(g["id"] for g in gpus if g.get("memory_bandwidth_gib_s"))
    quant_id = database.fetch_quantization_profiles()[0]["id"]

    response = client.post(
        "/v1/claims",
        json=_claim_payload(gpu_model_id=gpu_id, quantization_profile_id=quant_id),
        headers=_auth(token),
    ).json()
    roofline = response["prior_snapshot"]["roofline"]
    assert roofline is not None
    assert roofline["basis"] == "formula"
    assert roofline["expected_decode_tok_s"] > 0
    assert len(roofline["plausible_range"]) == 2


def test_create_claim_unknown_model_404_and_missing_metric_400(client, database, monkeypatch):
    token = _session_token(client, database, monkeypatch, HANDLE_A)
    unknown = client.post("/v1/claims", json=_claim_payload(model_release_id="nope"), headers=_auth(token))
    assert unknown.status_code == 404
    missing = client.post(
        "/v1/claims", json=_claim_payload(claimed_metrics={"prefill_tok_s": 100}), headers=_auth(token)
    )
    assert missing.status_code == 400


def test_claim_on_foreign_or_unknown_rig_404(client, database, monkeypatch):
    token_a = _session_token(client, database, monkeypatch, HANDLE_A)
    token_b = _session_token(client, database, monkeypatch, HANDLE_B)

    rig_a = client.post("/v1/rigs", json={"nickname": "Box A"}, headers=_auth(token_a)).json()

    foreign = client.post(
        "/v1/claims", json=_claim_payload(rig_slug=rig_a["slug"]), headers=_auth(token_b)
    )
    ghost = client.post(
        "/v1/claims", json=_claim_payload(rig_slug="ghost-rig"), headers=_auth(token_a)
    )
    assert foreign.status_code == 404
    assert ghost.status_code == 404


# --- voting ------------------------------------------------------------------


def test_vote_requires_auth_and_rejects_self_vote(client, database, monkeypatch):
    token_a = _session_token(client, database, monkeypatch, HANDLE_A)
    claim = client.post("/v1/claims", json=_claim_payload(), headers=_auth(token_a)).json()

    anonymous = client.post(f"/v1/claims/{claim['id']}/votes", json={"verdict": "plausible"})
    self_vote = client.post(
        f"/v1/claims/{claim['id']}/votes", json={"verdict": "plausible"}, headers=_auth(token_a)
    )
    assert anonymous.status_code == 401
    assert self_vote.status_code == 400


def test_votes_accumulate_with_tier_weights_and_upsert(client, database, monkeypatch):
    token_a = _session_token(client, database, monkeypatch, HANDLE_A)  # L0 → 0.2
    token_b = _session_token(client, database, monkeypatch, HANDLE_B)  # L0 → 0.2
    claim = client.post("/v1/claims", json=_claim_payload(), headers=_auth(token_a)).json()

    first = client.post(
        f"/v1/claims/{claim['id']}/votes", json={"verdict": "impossible"}, headers=_auth(token_b)
    ).json()
    assert first["tally"] == {
        "voter_count": 1,
        "plausible_count": 0,
        "impossible_count": 1,
        "plausible_weight": 0.0,
        "impossible_weight": 0.2,
        "margin": -0.2,
    }

    # same voter flips their verdict — count stays at one, margin flips sign
    flipped = client.post(
        f"/v1/claims/{claim['id']}/votes", json={"verdict": "plausible"}, headers=_auth(token_b)
    ).json()
    assert flipped["tally"]["voter_count"] == 1
    assert flipped["tally"]["margin"] == 0.2


def test_retract_only_by_claimant_and_only_open(client, database, monkeypatch):
    token_a = _session_token(client, database, monkeypatch, HANDLE_A)
    token_b = _session_token(client, database, monkeypatch, HANDLE_B)
    claim = client.post("/v1/claims", json=_claim_payload(), headers=_auth(token_a)).json()

    forbidden = client.post(f"/v1/claims/{claim['id']}/retract", headers=_auth(token_b))
    assert forbidden.status_code == 403

    retracted = client.post(f"/v1/claims/{claim['id']}/retract", headers=_auth(token_a)).json()
    assert retracted["status"] == "retracted"

    again = client.post(f"/v1/claims/{claim['id']}/retract", headers=_auth(token_a))
    assert again.status_code == 409  # not open anymore


def test_get_unknown_claim_404(client):
    assert client.get(f"/v1/claims/{uuid.uuid4()}").status_code == 404


# --- listing / sorting -------------------------------------------------------


def _lift_tier(database, handle: str, tier: str) -> None:
    user_id = database.find_app_user_by_handle(handle)["id"]
    for row in database._reputations:
        if row["app_user_id"] == user_id:
            row["tier"] = tier


def _create_n_claims(client, token, n):
    return [
        client.post("/v1/claims", json=_claim_payload(note=f"c{i}"), headers=_auth(token)).json()["id"]
        for i in range(n)
    ]


def test_listing_sorts_recent_controversial_strongest(client, database, monkeypatch):
    token_a = _session_token(client, database, monkeypatch, HANDLE_A)
    token_b = _session_token(client, database, monkeypatch, HANDLE_B)
    # lift above the L0 claim cap: this test is about sorting, not limits
    ada_id = database.find_app_user_by_handle(HANDLE_A)["id"]
    for row in database._reputations:
        if row["app_user_id"] == ada_id:
            row["tier"] = "L3"
    ids = _create_n_claims(client, token_a, 3)

    # claim 0 gets a vote (|margin| 0.2), claims 1 and 2 stay voteless (|margin| 0)
    client.post(f"/v1/claims/{ids[0]}/votes", json={"verdict": "plausible"}, headers=_auth(token_b))

    recent = client.get("/v1/claims?sort=recent").json()
    controversial = client.get("/v1/claims?sort=controversial").json()
    strongest = client.get("/v1/claims?sort=strongest").json()

    assert [c["id"] for c in recent][:3] == list(reversed(ids))
    assert controversial[-1]["id"] == ids[0]  # voted claim is least "controversial" here
    assert strongest[0]["id"] == ids[0]
    margins = [abs(c["tally"]["margin"]) for c in strongest]
    assert margins == sorted(margins, reverse=True)


def test_status_filter_on_listing(client, database, monkeypatch):
    token_a = _session_token(client, database, monkeypatch, HANDLE_A)
    ids = _create_n_claims(client, token_a, 2)
    client.post(f"/v1/claims/{ids[0]}/retract", headers=_auth(token_a))

    open_only = client.get("/v1/claims?status=open").json()
    retracted_only = client.get("/v1/claims?status=retracted").json()
    assert all(c["status"] == "open" for c in open_only)
    assert [c["id"] for c in retracted_only] == [ids[0]]


def test_invalid_sort_and_status_rejected(client):
    assert client.get("/v1/claims?sort=hotness").status_code == 400
    assert client.get("/v1/claims?status=vibes").status_code == 400


# --- S29: source_url (rede de captura) ---------------------------------------


def test_create_claim_persists_source_url(client, database, monkeypatch):
    token = _session_token(client, database, monkeypatch, HANDLE_A)
    reddit = "https://www.reddit.com/r/LocalLLaMA/comments/abc/my_3090_run/"
    created = client.post(
        "/v1/claims",
        json=_claim_payload(source_url=reddit),
        headers=_auth(token),
    ).json()
    assert created["source_url"] == reddit
    fetched = client.get(f"/v1/claims/{created['id']}").json()
    assert fetched["source_url"] == reddit


def test_create_claim_source_url_null_when_absent(client, database, monkeypatch):
    token = _session_token(client, database, monkeypatch, HANDLE_A)
    created = client.post("/v1/claims", json=_claim_payload(), headers=_auth(token)).json()
    assert created["source_url"] is None


def test_create_claim_rejects_non_http_source_url(client, database, monkeypatch):
    token = _session_token(client, database, monkeypatch, HANDLE_A)
    response = client.post(
        "/v1/claims",
        json=_claim_payload(source_url="olha o print anexo"),
        headers=_auth(token),
    )
    assert response.status_code == 422
