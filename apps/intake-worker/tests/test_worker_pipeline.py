import copy
import hashlib

from fixture_loader import load_fraudulent_run, load_valid_run
from worker import (
    STATUS_QUARANTINED,
    STATUS_REJECTED,
    STATUS_VALIDATED,
    process_run,
)


class FakeIntakeRepository:
    def __init__(self, duplicate_exists=False, peer_decode_values=None, peer_count=0):
        self.duplicate_exists = duplicate_exists
        self.peer_decode_values = peer_decode_values or []
        self.peer_count = peer_count
        self.assessments = {}
        self.statuses = {}
        self.ranking_updates = []

    def find_existing_run_in_group(self, dimension, exclude_run_id, statuses):
        return self.duplicate_exists

    def fetch_peer_decode_values(self, dimension, exclude_run_id):
        return list(self.peer_decode_values)

    def count_peers(self, dimension):
        return self.peer_count

    def record_trust_assessment(self, run_id, assessment):
        self.assessments[run_id] = assessment

    def set_run_status(self, run_id, status, trust_score):
        self.statuses[run_id] = (status, trust_score)

    def publish_ranking_update(self, event):
        self.ranking_updates.append(event)

    def fetch_run_payload(self, run_id):
        return None


def with_decode(payload, decode_value):
    payload = copy.deepcopy(payload)
    payload["metrics"]["decode_tok_s"] = decode_value
    for artifact in payload["artifacts"]:
        if artifact["artifact_kind"] != "runtime_stdout":
            continue
        lines = artifact["content"].splitlines()
        updated = [
            f"metric decode_tok_s {decode_value}" if line.startswith("metric decode_tok_s") else line
            for line in lines
        ]
        artifact["content"] = "\n".join(updated) + "\n"
        artifact["declared_sha256"] = hashlib.sha256(
            artifact["content"].encode("utf-8")
        ).hexdigest()
    return payload


def test_valid_run_is_validated_with_clean_flags():
    repository = FakeIntakeRepository()
    outcome = process_run(load_valid_run(), repository)
    assert outcome["status"] == STATUS_VALIDATED
    assert outcome["outlier_flags"] == []
    assert outcome["rejection_reasons"] == []
    assessment = outcome["trust_assessment"]
    assert assessment["outlier_flags"] == []
    for name, score in assessment.items():
        if isinstance(score, float):
            assert 0.0 <= score <= 1.0, name
    assert repository.assessments["run-valid-0001"] == assessment
    assert repository.statuses["run-valid-0001"][0] == STATUS_VALIDATED
    update = repository.ranking_updates[-1]
    assert update["run_id"] == "run-valid-0001"
    assert update["status"] == STATUS_VALIDATED
    assert "trust_score" in update


def test_fraudulent_run_is_quarantined_by_roofline_and_memory():
    repository = FakeIntakeRepository()
    outcome = process_run(load_fraudulent_run(), repository)
    assert outcome["status"] == STATUS_QUARANTINED
    assert "roofline_violation" in outcome["outlier_flags"]
    assert "impossible_memory_footprint" in outcome["outlier_flags"]
    assert repository.statuses["run-fraud-0001"][0] == STATUS_QUARANTINED


def test_invalid_signature_is_rejected():
    payload = load_valid_run()
    payload["signature_valid"] = False
    outcome = process_run(payload, FakeIntakeRepository())
    assert outcome["status"] == STATUS_REJECTED
    assert "invalid_signature" in outcome["rejection_reasons"]


def test_bad_schema_version_is_rejected():
    payload = load_valid_run()
    payload["schema_version"] = "0.5.0"
    outcome = process_run(payload, FakeIntakeRepository())
    assert outcome["status"] == STATUS_REJECTED
    assert "unsupported_schema_version" in outcome["rejection_reasons"]


def test_artifact_hash_mismatch_is_rejected():
    payload = load_valid_run()
    payload["artifacts"][0]["declared_sha256"] = "0" * 64
    outcome = process_run(payload, FakeIntakeRepository())
    assert outcome["status"] == STATUS_REJECTED
    assert any(reason.startswith("artifact_hash_mismatch") for reason in outcome["rejection_reasons"])


def test_duplicate_dimension_group_is_rejected():
    repository = FakeIntakeRepository(duplicate_exists=True)
    outcome = process_run(load_valid_run(), repository)
    assert outcome["status"] == STATUS_REJECTED
    assert "duplicate_submission" in outcome["rejection_reasons"]


def test_statistical_outlier_is_quarantined():
    payload = with_decode(load_valid_run(), 120.0)
    repository = FakeIntakeRepository(peer_decode_values=[90.0, 91.0, 92.0])
    outcome = process_run(payload, repository)
    assert outcome["status"] == STATUS_QUARANTINED
    assert outcome["outlier_flags"] == ["statistical_outlier"]
