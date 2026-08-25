"""S20 tests: embeddable verified-run badges + reputation-scaled rate limits."""

from __future__ import annotations

import uuid

import pytest

from conftest import make_passkey_session
from src.main import create_app
from src.services.render_run_badge import render_run_badge

HANDLE_A = "ada"


@pytest.fixture()
def client(database):
    app = create_app()
    from fastapi.testclient import TestClient
    from src.dependencies.database_session_provider import get_database_session

    app.dependency_overrides[get_database_session] = lambda: database
    with TestClient(app) as test_client:
        yield test_client


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- badges ------------------------------------------------------------------


def test_badge_renders_for_validated_run(client, database):
    gpu_id = database.fetch_all_gpus()[0]["id"]
    gpu_name = database.fetch_all_gpus()[0]["marketing_name"]
    hardware_id = "00000000-0000-0000-0000-000000000010"
    database.insert_hardware_submission(
        {
            "id": hardware_id,
            "owner_account_id": "00000000-0000-0000-0000-000000000099",
            "gpu_model_id": gpu_id,
            "cpu_model_id": None,
            "gpu_count": 1,
            "ram_gib": 64,
            "os_name": "Linux",
            "os_version": "6.9",
            "environment_snapshot": {},
        }
    )
    run_id = str(uuid.uuid4())
    database._runs[0] = {**database._runs[0], "id": run_id, "hardware_submission_id": hardware_id}
    database._metrics.append(
        {"benchmark_run_id": run_id, "kind": "decode_tok_s", "p50_value": 41.7, "unit": "tok/s"}
    )

    response = client.get(f"/v1/badges/runs/{run_id}.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    body = response.text
    assert "41.7 tok/s" in body
    assert gpu_name in body
    assert "<script" not in body


def test_badge_404_for_unknown_or_unvalidated_runs(client, database):
    assert client.get(f"/v1/badges/runs/{uuid.uuid4()}.svg").status_code == 404
    # a submitted (not validated) run earns no badge
    unvalidated = str(uuid.uuid4())
    database._runs.append(
        {
            "id": unvalidated,
            "hardware_submission_id": "whatever",
            "model_release_id": "model-qwen25-coder-7b",
            "quantization_profile_id": "q-fp16",
            "inference_runtime_id": "llama-cpp",
            "benchmark_scenario_id": "scen",
            "status": "submitted",
            "submitted_at": "2026-08-01T00:00:00Z",
        }
    )
    assert client.get(f"/v1/badges/runs/{unvalidated}.svg").status_code == 404


def test_badge_renderer_is_exact_and_escapes():
    svg = render_run_badge(
        {
            "run_id": "r1",
            "status": "validated",
            "model_release_id": 'm"<x>',
            "decode_tok_s": 41.75,
            "gpu_marketing_name": "RTX 3090",
        }
    )
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="')
    assert '41.8 tok/s on RTX 3090' in svg
    assert '<x>' not in svg


# --- rate limits -------------------------------------------------------------


def _open_claim(client, token, model="model-qwen25-coder-7b"):
    return client.post(
        "/v1/claims",
        json={"model_release_id": model, "claimed_metrics": {"decode_tok_s": 18.7}},
        headers=_auth(token),
    )


def test_claim_rate_limit_blocks_l0_after_two(client, database, monkeypatch):
    token = make_passkey_session(client, database, monkeypatch, HANDLE_A)

    first = _open_claim(client, token)
    second = _open_claim(client, token)
    third = _open_claim(client, token)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert "raise your ceiling" in third.json()["detail"]

    # reputation upgrade lifts the ceiling immediately
    user_id = database.find_app_user_by_handle(HANDLE_A)["id"]
    for row in database._reputations:
        if row["app_user_id"] == user_id:
            row["tier"] = "L2"
    fourth = _open_claim(client, token)
    assert fourth.status_code == 200


def test_vote_rate_limit_blocks_at_tier_ceiling(client, database, monkeypatch):
    """L3 ceiling is 100/hour: pre-seed 99 votes in-window, then hit the wall."""
    from datetime import datetime, timezone

    from src.services.auth_common import hours_ago_iso

    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    token_b = make_passkey_session(client, database, monkeypatch, "grace")
    grace_id = database.find_app_user_by_handle("grace")["id"]
    for row in database._reputations:
        if row["app_user_id"] == grace_id:
            row["tier"] = "L3"

    claim = _open_claim(client, token_a).json()
    now_iso = datetime.now(timezone.utc).isoformat()

    def seed_vote(nth):
        database._votes.append(
            {
                "id": str(uuid.uuid4()),
                "run_claim_id": f"seeded-{nth}",
                "voter_id": grace_id,
                "verdict": "plausible",
                "weight": 0.8,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )

    for i in range(99):
        seed_vote(i)

    ok = client.post(
        f"/v1/claims/{claim['id']}/votes", json={"verdict": "plausible"}, headers=_auth(token_b)
    )
    assert ok.status_code == 200  # the 100th vote this hour fits

    blocked = client.post(f"/v1/claims/{claim['id']}/votes", json={"verdict": "impossible"}, headers=_auth(token_b))
    assert blocked.status_code == 429
    assert "vote limit reached" in blocked.json()["detail"]
    assert hours_ago_iso(1)
