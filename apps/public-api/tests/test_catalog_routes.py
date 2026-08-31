from __future__ import annotations

from fastapi.testclient import TestClient


def test_catalog_routes_are_public(client: TestClient) -> None:
    assert client.get("/v1/model-releases").status_code == 200
    assert client.get("/v1/quantization-profiles").status_code == 200


def test_model_release_catalog_shape_and_contents(client: TestClient) -> None:
    payload = client.get("/v1/model-releases").json()
    assert payload["count"] == len(payload["items"]) > 0
    expected_keys = {
        "id",
        "release_name",
        "family",
        "parameter_count_billion",
        "max_context_tokens",
    }
    assert all(set(row) == expected_keys for row in payload["items"])
    item = next(row for row in payload["items"] if row["id"] == "model-qwen25-coder-32b")
    assert item["release_name"] == "Qwen2.5-Coder-32B"
    assert [row["id"] for row in payload["items"]] == sorted(row["id"] for row in payload["items"])


def test_quantization_profile_catalog_shape_and_contents(client: TestClient) -> None:
    payload = client.get("/v1/quantization-profiles").json()
    assert payload["count"] == len(payload["items"]) > 0
    expected_keys = {"id", "display_name", "weight_format", "weight_bits"}
    assert all(set(row) == expected_keys for row in payload["items"])
    item = next(row for row in payload["items"] if row["id"] == "q-fp16")
    assert item["display_name"] == "FP16"
    assert [row["id"] for row in payload["items"]] == sorted(row["id"] for row in payload["items"])
