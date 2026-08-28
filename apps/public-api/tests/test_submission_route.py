"""Route tests for GET /v1/submissions/nonce and POST /v1/submissions."""

from __future__ import annotations

import hashlib
import json
import uuid

from conftest import sample_report_dict, sign_report


def _multipart(report_dict, private_key, artifact_bytes, **overrides):
    digest, signature = sign_report(private_key, report_dict)
    data = {
        "report": json.dumps(report_dict),
        "signature": signature,
        "payload_digest": digest,
        "challenge_nonce": "nonce-abc",
        "client_version": "0.1.0",
    }
    data.update(overrides)
    files = [
        (f"artifact_{index}", (f"artifact_{index}", content, "application/octet-stream"))
        for index, content in enumerate(artifact_bytes)
    ]
    return data, files


def test_nonce_returns_uuid(client):
    response = client.get("/v1/submissions/nonce")
    assert response.status_code == 200
    nonce = response.json()["challenge_nonce"]
    uuid.UUID(nonce)


def test_valid_submission_returns_202_with_run_id(client, database, artifact_vault, benchmark_queue, trusted_key):
    report = sample_report_dict()
    data, files = _multipart(report, trusted_key, [b"stdout log"])
    response = client.post("/v1/submissions", data=data, files=files)
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    assert run_id
    assert len(benchmark_queue.events) == 1
    assert benchmark_queue.events[0]["run_id"] == run_id
    assert database.find_hardware_submission(hashlib.sha256(b"n/a").hexdigest()[:32]) is None
    assert any(run["id"] == run_id and run["status"] == "submitted" for run in database._runs)
    assert len(database._metrics) == 5
    assert len(database._artifacts) == 1
    assert artifact_vault.retrieve(f"{report['run_id']}/artifact_0") == b"stdout log"


def test_duplicate_submission_returns_409(client, trusted_key):
    report = sample_report_dict()
    data, files = _multipart(report, trusted_key, [b"stdout log"])
    first = client.post("/v1/submissions", data=data, files=files)
    assert first.status_code == 202
    second = client.post("/v1/submissions", data=data, files=files)
    assert second.status_code == 409
    assert "duplicate" in second.json()["detail"]


def test_invalid_report_json_returns_400(client, trusted_key):
    data = {
        "report": "{not json",
        "signature": "00",
        "payload_digest": "00",
        "challenge_nonce": "nonce-abc",
        "client_version": "0.1.0",
    }
    response = client.post("/v1/submissions", data=data, files=[])
    assert response.status_code == 400
    assert "JSON" in response.json()["detail"]


def test_schema_invalid_report_returns_400_with_details(client, trusted_key):
    report = sample_report_dict()
    report["metrics"]["decode_tok_s"] = -5.0
    data, files = _multipart(report, trusted_key, [b"stdout log"])
    response = client.post("/v1/submissions", data=data, files=files)
    assert response.status_code == 400
    assert "schema validation" in response.json()["detail"]


def test_payload_digest_mismatch_returns_400(client, trusted_key):
    report = sample_report_dict()
    data, files = _multipart(report, trusted_key, [b"stdout log"])
    data["payload_digest"] = "0" * 64
    response = client.post("/v1/submissions", data=data, files=files)
    assert response.status_code == 400
    assert "payload_digest" in response.json()["detail"]


def test_invalid_signature_returns_400(client, trusted_key):
    report = sample_report_dict()
    data, files = _multipart(report, trusted_key, [b"stdout log"])
    data["signature"] = "0" * 128
    response = client.post("/v1/submissions", data=data, files=files)
    assert response.status_code == 400
    assert "signature" in response.json()["detail"]


def test_artifact_digest_mismatch_returns_400(client, trusted_key):
    report = sample_report_dict()
    report["artifacts"][0]["sha256"] = hashlib.sha256(b"different content").hexdigest()
    data, files = _multipart(report, trusted_key, [b"stdout log"])
    response = client.post("/v1/submissions", data=data, files=files)
    assert response.status_code == 400
    assert "digest" in response.json()["detail"]


def test_artifact_count_mismatch_returns_400(client, trusted_key):
    report = sample_report_dict()
    data, files = _multipart(report, trusted_key, [])
    response = client.post("/v1/submissions", data=data, files=files)
    assert response.status_code == 400
    assert "artifacts" in response.json()["detail"]


def test_missing_form_fields_returns_400(client, trusted_key):
    response = client.post(
        "/v1/submissions",
        data={"report": json.dumps(sample_report_dict())},
        files=[],
    )
    assert response.status_code == 400
    assert "submission fields" in response.json()["detail"]


def sample_video_report_dict() -> dict:
    """A valid comfyui video report referencing the seed recipe (Épico 1)."""
    return {
        "schema_version": "0.9.0",
        "run_id": "01J9XYZTEST00000000000000V1",
        "runtime": "comfyui",
        "runtime_version": "comfy-cli 0.3.48",
        "hardware_fingerprint": "sha256:abcdef0123456789",
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
        "metrics": {
            "ttft_ms": 0.0,
            "prefill_tok_s": 0.0,
            "decode_tok_s": 0.0,
            "peak_vram_mib": 22000,
            "power_watt_avg": 0.0,
            "seconds_per_clip": 123.4,
            "it_per_s": 10.0,
            "frames_per_s": 0.66,
        },
        "artifacts": [
            {"artifact_kind": "runtime_stdout", "sha256": hashlib.sha256(b"comfy log").hexdigest()}
        ],
        "recipe_id": "wan22-flf2v-720p-81f-v1",
    }


def test_video_submission_persists_recipe_and_video_fields(
    client, database, artifact_vault, benchmark_queue, trusted_key
):
    report = sample_video_report_dict()
    data, files = _multipart(report, trusted_key, [b"comfy log"])
    response = client.post("/v1/submissions", data=data, files=files)
    assert response.status_code == 202, response.json()
    run = database._runs[-1]
    assert run["recipe_id"] == "wan22-flf2v-720p-81f-v1"
    assert run["source_class"] == "measured_signed"
    assert run["seconds_per_clip"] == 123.4
    assert run["it_per_s"] == 10.0
    assert run["frames_per_s"] == 0.66
    scenario = database._scenarios[-1]
    assert scenario["scenario_kind"] == "video"
    assert scenario["frames"] == 81
    assert scenario["width"] == 1280
    assert scenario["prompt_tokens"] is None
    # Video metrics are scalars on the run, not benchmark_metric rows.
    assert all(metric["kind"] not in ("seconds_per_clip", "it_per_s", "frames_per_s")
               for metric in database._metrics)


def test_video_submission_with_unknown_recipe_returns_400(client, trusted_key):
    report = sample_video_report_dict()
    report["recipe_id"] = "no-such-recipe"
    data, files = _multipart(report, trusted_key, [b"comfy log"])
    response = client.post("/v1/submissions", data=data, files=files)
    assert response.status_code == 400
    assert "unknown recipe_id" in response.json()["detail"]


def test_llm_report_without_recipe_still_accepted(client, trusted_key):
    report = sample_report_dict()
    assert "recipe_id" not in report
    data, files = _multipart(report, trusted_key, [b"stdout log"])
    response = client.post("/v1/submissions", data=data, files=files)
    assert response.status_code == 202
    assert database_runs_last(client)["recipe_id"] is None


def database_runs_last(client) -> dict:
    # The client fixture closes over its own FakeDatabase; re-read via the app
    # dependency override to reach the same instance.
    from src.dependencies.database_session_provider import get_database_session

    app = client._transport.app  # TestClient's ASGI app
    session = app.dependency_overrides[get_database_session]()
    return session._runs[-1]
