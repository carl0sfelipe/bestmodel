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
