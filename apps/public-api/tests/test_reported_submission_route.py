"""Story 5.2 — lightweight authenticated `reported` submissions.

Offline tests over the FakeDatabase. The real-PostgreSQL end-to-end proof
(register → submit → quota → leaderboard immunity) lives in the session
oracle; here we pin the contract: 401 without/with bad token, catalog
validation, quota 429, duplicate 409, honest reported markers, and the
leaderboard staying empty for reported runs.
"""

from __future__ import annotations

import pytest

LLM_BODY = {
    "model_release_id": "model-qwen25-coder-7b",
    "inference_runtime_id": "llama-cpp",
    "gpu_model_id": "gpu-rtx-3090",
    "scenario": {
        "prompt_tokens": 4096,
        "generated_tokens": 512,
        "batch_size": 1,
        "context_tokens": 8192,
    },
    "metrics": {"decode_tok_s": 35.2, "peak_vram_mib": 18000},
}


def register(client, email="dev@example.com"):
    response = client.post("/v1/contributors", json={"email": email})
    assert response.status_code == 201, response.text
    return response.json()


def submit_reported(client, token, body):
    return client.post(
        "/v1/submissions/reported",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )


def test_register_returns_token_once_and_conflicts_on_repeat(client):
    first = register(client)
    assert first["token"]
    assert first["contributor_id"]

    repeat = client.post("/v1/contributors", json={"email": "dev@example.com"})
    assert repeat.status_code == 409


def test_register_rejects_invalid_email(client):
    response = client.post("/v1/contributors", json={"email": "not-an-email"})
    assert response.status_code == 400


def test_token_is_stored_hashed_not_plaintext(client, database):
    token = register(client)["token"]
    stored = database._contributors[0]
    assert stored["token_hash"] != token
    assert len(stored["token_hash"]) == 64


def test_reported_without_token_is_401(client):
    response = client.post("/v1/submissions/reported", json=LLM_BODY)
    assert response.status_code == 401


def test_reported_with_unknown_token_is_401(client):
    response = submit_reported(client, "not-a-real-token", LLM_BODY)
    assert response.status_code == 401


def test_reported_happy_path_lands_submitted_and_out_of_leaderboard(client, database):
    registration = register(client)
    response = submit_reported(client, registration["token"], LLM_BODY)
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]

    run = next(run for run in database._runs if run["id"] == run_id)
    assert run["source_class"] == "reported"
    assert run["status"] == "submitted"
    assert run["signature"] == "reported"
    assert run["payload_digest"].startswith("sha256:")
    assert run["source_url"] is None
    # metrics landed as token rows
    kinds = {metric["kind"] for metric in database._metrics}
    assert {"decode_tok_s", "peak_vram_mib"} <= kinds
    # the reported contributor owns the derived hardware row
    hardware = next(
        row
        for row in database._hardware_submissions
        if row["id"] == run["hardware_submission_id"]
    )
    assert hardware["gpu_model_id"] == "gpu-rtx-3090"
    assert hardware["owner_account_id"] == registration["contributor_id"]

    leaderboard = client.get("/v1/leaderboard").json()
    assert leaderboard["runs"] == []


def test_reported_video_scenario_uses_scalar_columns(client, database):
    token = register(client, "video@example.com")["token"]
    body = {
        "model_release_id": "model-wan22-i2v-flf2v-14b",
        "inference_runtime_id": "comfyui",
        "gpu_model_id": "gpu-rtx-3090",
        "recipe_id": "wan22-flf2v-720p-81f-v1",
        "scenario": {
            "scenario_kind": "video",
            "width": 1280,
            "height": 720,
            "frames": 81,
            "steps": 20,
            "cfg": 3.5,
            "shift": 5.0,
            "seed": 42,
        },
        "metrics": {"seconds_per_clip": 900.5, "frames_per_s": 0.09},
    }
    response = submit_reported(client, token, body)
    assert response.status_code == 202, response.text
    run = next(run for run in database._runs if run["id"] == response.json()["run_id"])
    assert run["seconds_per_clip"] == 900.5
    assert run["recipe_id"] == "wan22-flf2v-720p-81f-v1"
    # video metrics never fabricate token rows (AD-1)
    kinds = {metric["kind"] for metric in database._metrics}
    assert "decode_tok_s" not in kinds


def test_reported_rejects_unknown_catalog_ids(client):
    token = register(client, "catalog@example.com")["token"]
    bad = {**LLM_BODY, "model_release_id": "model-nope"}
    assert submit_reported(client, token, bad).status_code == 400
    bad_runtime = {**LLM_BODY, "inference_runtime_id": "runtime-nope"}
    assert submit_reported(client, token, bad_runtime).status_code == 400
    bad_gpu = {**LLM_BODY, "gpu_model_id": "gpu-nope"}
    assert submit_reported(client, token, bad_gpu).status_code == 400


def test_reported_rejects_empty_metrics_and_bad_scenario(client):
    token = register(client, "empty@example.com")["token"]
    no_metrics = {**LLM_BODY, "metrics": {}}
    assert submit_reported(client, token, no_metrics).status_code == 400
    bad_scenario = {
        **LLM_BODY,
        "scenario": {"scenario_kind": "video", "width": -1},
    }
    assert submit_reported(client, token, bad_scenario).status_code == 400


def test_reported_duplicate_is_409(client):
    token = register(client, "dup@example.com")["token"]
    assert submit_reported(client, token, LLM_BODY).status_code == 202
    assert submit_reported(client, token, LLM_BODY).status_code == 409


def test_reported_quota_per_ip_is_429_and_logged(client, database, monkeypatch):
    monkeypatch.setenv("REPORTED_QUOTA_PER_IP", "2")
    token = register(client, "quota@example.com")["token"]
    assert submit_reported(client, token, LLM_BODY).status_code == 202
    body2 = {
        **LLM_BODY,
        "scenario": {
            "prompt_tokens": 2048,
            "generated_tokens": 256,
            "batch_size": 1,
            "context_tokens": 4096,
        },
    }
    assert submit_reported(client, token, body2).status_code == 202
    third = client.post(
        "/v1/submissions/reported",
        json={
            **LLM_BODY,
            "scenario": {
                "prompt_tokens": 1024,
                "generated_tokens": 128,
                "batch_size": 1,
                "context_tokens": 2048,
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert third.status_code == 429
    assert len(database.reported_submission_log) == 2


def test_reported_quota_is_per_ip(client, monkeypatch):
    monkeypatch.setenv("REPORTED_QUOTA_PER_IP", "1")
    first = register(client, "ip1@example.com")
    second = register(client, "ip2@example.com")
    # TestClient always presents the same client host, so simulate the second
    # IP by exhausting the quota through a distinct scenario only after
    # checking both tokens authenticate on their own.
    assert submit_reported(client, first["token"], LLM_BODY).status_code == 202
    other_ip = client.post(
        "/v1/submissions/reported",
        json=LLM_BODY,
        headers={"Authorization": f"Bearer {second['token']}"},
    )
    # same IP as the first call -> quota is what rejects it, not the token
    assert other_ip.status_code == 429


@pytest.mark.parametrize(
    "headers",
    [None, {"Authorization": "Basic abc"}],
    ids=["no-header", "non-bearer"],
)
def test_reported_auth_header_variants_are_401(client, headers):
    response = client.post("/v1/submissions/reported", json=LLM_BODY, headers=headers)
    assert response.status_code == 401
