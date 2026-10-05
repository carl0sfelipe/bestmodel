"""Route tests for POST /v1/match/hardware-to-models."""

from __future__ import annotations

EXPECTED_FIELDS = {
    "model_release_id",
    "quantization_profile_id",
    "runtime_id",
    "feasible",
    "expected_decode_tok_s",
    "expected_prefill_tok_s",
    "expected_ttft_ms_8k_prompt",
    "expected_peak_vram_gib",
    "max_context_tokens",
    "quality_retention_estimate",
    "trust_score",
}


def _request(gpu_model_ids=None, **overrides):
    payload = {
        "gpu_model_ids": gpu_model_ids or ["gpu-rtx-4090"],
        "gpu_count": 2,
        "ram_gib": 96,
        "os_name": "ubuntu-22.04",
        "target_model_family": "qwen-2.5-coder",
        "target_context_tokens": 32768,
        "priority": "balanced",
    }
    payload.update(overrides)
    return payload


def test_returns_matches_with_section_9_4_fields(client):
    response = client.post("/v1/match/hardware-to-models", json=_request())
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"matches"}
    assert len(body["matches"]) > 0
    for match in body["matches"]:
        assert set(match.keys()) == EXPECTED_FIELDS
        assert isinstance(match["feasible"], bool)
        assert match["trust_score"] == 0.5


def test_unknown_gpu_ids_return_empty_matches(client):
    response = client.post(
        "/v1/match/hardware-to-models",
        json=_request(gpu_model_ids=["gpu-does-not-exist"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matches"] == []
    assert body["reason"] == "unknown_gpu_model_ids"
    assert "gpu-does-not-exist" in body["unknown_gpu_model_ids"]
    assert len(body["valid_gpu_model_ids"]) > 0


def test_unknown_gpu_ids_prefer_shared_tokens(client):
    response = client.post(
        "/v1/match/hardware-to-models",
        json=_request(gpu_model_ids=["gpu-a100"]),
    )
    body = response.json()
    assert body["reason"] == "unknown_gpu_model_ids"
    assert body["unknown_gpu_model_ids"] == ["gpu-a100"]
    assert body["valid_gpu_model_ids"][:2] == ["gpu-a100-40gb", "gpu-a100-80gb"]


def test_unknown_family_returns_empty_matches(client):
    response = client.post(
        "/v1/match/hardware-to-models",
        json=_request(target_model_family="no-such-family"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matches"] == []
    assert body["reason"] == "unknown_model_family"
    assert "qwen-2.5-coder" in body["valid_model_families"]


def test_unknown_family_lists_closest_families(client):
    response = client.post(
        "/v1/match/hardware-to-models",
        json=_request(target_model_family="qwen"),
    )
    body = response.json()
    assert body["reason"] == "unknown_model_family"
    assert "qwen-2.5-coder" in body["closest_model_families"]
    assert len(body["closest_model_families"]) <= 5


def test_rejects_invalid_request_payload(client):
    response = client.post(
        "/v1/match/hardware-to-models",
        json=_request(target_context_tokens=0),
    )
    assert response.status_code == 422


def _release(**overrides):
    row = {
        "id": "model-ok-dense",
        "family": "fixture-moe-gap",
        "release_name": "Ok-Dense",
        "architecture": "dense",
        "parameter_count_billion": 7.0,
        "active_parameter_count_billion": None,
        "num_layers": 32,
        "hidden_size": 4096,
        "num_attention_heads": 32,
        "num_kv_heads": 8,
        "head_dim": 128,
        "expert_count": None,
        "experts_per_token": None,
        "max_context_tokens": 8192,
        "released_at": "2026-01-01",
    }
    row.update(overrides)
    return row


def test_skips_moe_missing_active_params_and_returns_dense(client, database, caplog):
    database._models.extend(
        [
            _release(
                id="model-broken-moe",
                release_name="Broken-MoE",
                architecture="moe",
                parameter_count_billion=26.0,
                expert_count=128,
            ),
            _release(),
        ]
    )
    with caplog.at_level("WARNING"):
        response = client.post(
            "/v1/match/hardware-to-models",
            json=_request(target_model_family="fixture-moe-gap", gpu_count=1),
        )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"matches"}
    model_ids = {match["model_release_id"] for match in body["matches"]}
    assert "model-ok-dense" in model_ids
    assert "model-broken-moe" not in model_ids
    assert "model-broken-moe" in caplog.text


def test_no_feasible_candidate_explains_empty_answer(client, database):
    database._models.extend(
        [
            _release(
                id="model-broken-moe-1",
                family="fixture-all-broken",
                release_name="Broken-MoE-1",
                architecture="moe",
                parameter_count_billion=26.0,
                expert_count=128,
            ),
            _release(
                id="model-broken-moe-2",
                family="fixture-all-broken",
                release_name="Broken-MoE-2",
                architecture="moe",
                parameter_count_billion=32.0,
                expert_count=128,
            ),
        ]
    )
    response = client.post(
        "/v1/match/hardware-to-models",
        json=_request(target_model_family="fixture-all-broken", gpu_count=1),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["matches"] == []
    assert body["reason"] == "no_feasible_candidate"
    assert body["skipped_candidates"] == 2 * len(
        database.fetch_quantization_profiles()
    ) * len(database.fetch_inference_runtimes())
