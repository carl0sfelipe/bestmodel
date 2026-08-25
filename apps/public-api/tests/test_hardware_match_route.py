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
    assert "matches" in body
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
    assert response.json() == {"matches": []}


def test_unknown_family_returns_empty_matches(client):
    response = client.post(
        "/v1/match/hardware-to-models",
        json=_request(target_model_family="no-such-family"),
    )
    assert response.status_code == 200
    assert response.json() == {"matches": []}


def test_rejects_invalid_request_payload(client):
    response = client.post(
        "/v1/match/hardware-to-models",
        json=_request(target_context_tokens=0),
    )
    assert response.status_code == 422
