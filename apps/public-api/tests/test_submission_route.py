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
