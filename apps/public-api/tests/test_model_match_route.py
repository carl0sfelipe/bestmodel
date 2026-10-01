"""Route tests for POST /v1/match/model-to-hardware."""

from __future__ import annotations

EXPECTED_FIELDS = {
    "gpu_model_id",
    "gpu_count",
    "quantization_profile_id",
    "runtime_id",
    "feasible",
    "expected_peak_vram_gib",
    "expected_decode_tok_s",
    "expected_prefill_tok_s",
    "max_context_tokens",
}


def _request(**overrides):
    payload = {
        "model_release_id": "model-qwen25-coder-32b",
        "target_context_tokens": 32768,
        "batch_size": 1,
        "priority": "balanced",
    }
    payload.update(overrides)
    return payload


def test_returns_configured_roles_with_expected_fields(client):
    response = client.post("/v1/match/model-to-hardware", json=_request())
    assert response.status_code == 200
    body = response.json()
    assert "configs" in body
    configs = body["configs"]
    assert len(configs) > 0
    roles = {config["role"] for config in configs}
    assert roles <= {"minimum", "recommended", "cost_efficient"}
    for config in configs:
        assert EXPECTED_FIELDS <= set(config.keys())
        assert config["feasible"] is True
        assert config["gpu_count"] >= 1


def test_unknown_model_returns_empty_configs(client):
    response = client.post(
        "/v1/match/model-to-hardware",
        json=_request(model_release_id="model-does-not-exist"),
    )
    assert response.status_code == 200
    assert response.json() == {"configs": []}


def test_impossible_context_returns_empty_configs(client):
    response = client.post(
        "/v1/match/model-to-hardware",
        json=_request(target_context_tokens=2_000_000),
    )
    assert response.status_code == 200
    assert response.json() == {"configs": []}


def test_rejects_invalid_request_payload(client):
    response = client.post("/v1/match/model-to-hardware", json=_request(batch_size=0))
    assert response.status_code == 422


def test_seed_moe_missing_experts_per_token_batch_returns_200(client):
    # Live catalog hole: model-gemma-4-26b-a4b-it is MoE with experts_per_token
    # null. batch_size>1 used to TypeError inside decode (API 500).
    response = client.post(
        "/v1/match/model-to-hardware",
        json=_request(
            model_release_id="model-gemma-4-26b-a4b-it",
            target_context_tokens=8192,
            batch_size=2,
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert "configs" in body
    for config in body["configs"]:
        assert EXPECTED_FIELDS <= set(config.keys())
        assert config["feasible"] is True
        assert config["expected_decode_tok_s"] > 0


def test_moe_missing_active_params_returns_empty_not_500(client, database):
    database._models.append(
        {
            "id": "model-broken-moe",
            "family": "fixture-moe-gap",
            "release_name": "Broken-MoE",
            "architecture": "moe",
            "parameter_count_billion": 26.0,
            "active_parameter_count_billion": None,
            "num_layers": 32,
            "hidden_size": 4096,
            "num_attention_heads": 32,
            "num_kv_heads": 8,
            "head_dim": 128,
            "expert_count": 128,
            "experts_per_token": None,
            "max_context_tokens": 8192,
            "released_at": "2026-01-01",
        }
    )
    response = client.post(
        "/v1/match/model-to-hardware",
        json=_request(model_release_id="model-broken-moe", batch_size=1),
    )
    assert response.status_code == 200
    assert response.json() == {"configs": []}
