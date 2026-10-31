"""B1: validated runs are anchored in the EaaS engine (kind=benchmark).

Contract under test:
- canonical digest is reproducible and key-order independent;
- anchoring happens ONLY for validated runs, with studio bestmodel;
- anchor failure (engine down, bad key) never fails validation;
- absent EAAS_API_KEY disables anchoring entirely.
"""

import hashlib
import json

import pytest
from fixture_loader import load_valid_run

from anchor_run import (
    STUDIO_ID,
    anchor_config,
    anchor_validated_run,
    canonical_run_digest,
)
from worker import STATUS_VALIDATED, process_run


class RecordingRepo:
    def __init__(self):
        self.anchors = {}

    def record_anchor(self, run_id, digest, record_id, studio_id):
        self.anchors[run_id] = {
            "digest": digest,
            "record_id": record_id,
            "studio_id": studio_id,
        }


from test_worker_pipeline import FakeIntakeRepository


def test_canonical_digest_is_order_independent_and_reproducible():
    payload = load_valid_run()
    a = {"z": 1, "a": {"y": [1, 2], "x": "s"}}
    b = {"a": {"x": "s", "y": [1, 2]}, "z": 1}
    assert canonical_run_digest(a) == canonical_run_digest(b)
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert canonical_run_digest(payload) == expected


def test_anchor_validated_run_posts_record_and_persists(monkeypatch):
    monkeypatch.setenv("EAAS_API_KEY", "eak_stg_teste")
    monkeypatch.setenv("EAAS_VERIFY_URL", "http://verify.test")
    calls = []

    def fake_post(url, body, bearer):
        calls.append({"url": url, "body": body, "bearer": bearer})
        return {"record_id": "rc_" + "a" * 24, "duplicate": False}

    repo = RecordingRepo()
    payload = load_valid_run()
    receipt = anchor_validated_run(payload["run_id"], payload, repo, http_post=fake_post)

    assert receipt["record_id"].startswith("rc_")
    assert calls[0]["url"] == "http://verify.test/v1/records"
    assert calls[0]["bearer"] == "eak_stg_teste"
    body = calls[0]["body"]
    assert body["studio_id"] == STUDIO_ID == "bestmodel"
    assert body["kind"] == "benchmark"
    assert body["digest"] == canonical_run_digest(payload)
    assert body["reference"] == payload["run_id"]
    assert repo.anchors[payload["run_id"]]["record_id"] == receipt["record_id"]


def test_anchor_disabled_without_api_key(monkeypatch):
    monkeypatch.delenv("EAAS_API_KEY", raising=False)
    assert anchor_config()[0] is None
    repo = RecordingRepo()
    assert anchor_validated_run("r1", {"x": 1}, repo, http_post=_boom) is None
    assert repo.anchors == {}


def test_engine_down_never_fails_validation(monkeypatch):
    monkeypatch.setenv("EAAS_API_KEY", "eak_stg_teste")
    payload = load_valid_run()
    repo = FakeIntakeRepository()

    def boom(url, body, bearer):
        raise ConnectionError("engine fora do ar")

    import anchor_run

    original = anchor_run._urllib_post
    anchor_run._urllib_post = boom
    try:
        result = process_run(payload, repo)
    finally:
        anchor_run._urllib_post = original
    assert result["status"] == STATUS_VALIDATED, "validação sobrevive sem âncora"
    assert repo.anchors == {}


def test_validated_run_gets_anchored_end_to_end(monkeypatch):
    monkeypatch.setenv("EAAS_API_KEY", "eak_stg_teste")
    payload = load_valid_run()
    repo = FakeIntakeRepository()

    def fake_post(url, body, bearer):
        return {"record_id": "rc_" + "b" * 24, "duplicate": False}

    import anchor_run

    original = anchor_run._urllib_post
    anchor_run._urllib_post = fake_post
    try:
        result = process_run(payload, repo)
    finally:
        anchor_run._urllib_post = original
    assert result["status"] == STATUS_VALIDATED
    anchor = repo.anchors[payload["run_id"]]
    assert anchor["digest"] == canonical_run_digest(payload)
    assert anchor["studio_id"] == "bestmodel"


def _boom(*args, **kwargs):
    raise AssertionError("HTTP não deve ser chamado com anchoring desligado")
