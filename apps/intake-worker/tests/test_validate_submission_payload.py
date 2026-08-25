from fixture_loader import load_valid_run
from validate_submission_payload import validate_submission_payload
from worker_models import build_run_record


def tamper(payload: dict, **fields) -> dict:
    payload = dict(payload)
    payload.update(fields)
    return payload


def test_valid_payload_has_no_rejections():
    record = build_run_record(load_valid_run())
    assert validate_submission_payload(record) == []


def test_invalid_signature_is_rejected():
    record = build_run_record(tamper(load_valid_run(), signature_valid=False))
    assert "invalid_signature" in validate_submission_payload(record)


def test_unsupported_schema_version_is_rejected():
    record = build_run_record(tamper(load_valid_run(), schema_version="0.8.0"))
    assert "unsupported_schema_version" in validate_submission_payload(record)


def test_missing_runtime_version_is_rejected():
    record = build_run_record(tamper(load_valid_run(), runtime_version=None))
    assert "missing_runtime_version" in validate_submission_payload(record)


def test_short_duration_is_rejected():
    record = build_run_record(tamper(load_valid_run(), duration_seconds=2.0))
    assert "benchmark_duration_too_short" in validate_submission_payload(record)


def test_high_throughput_short_duration_is_consistent():
    payload = tamper(load_valid_run(), duration_seconds=4.0)
    payload["metrics"]["decode_tok_s"] = 140.0
    reasons = validate_submission_payload(build_run_record(payload))
    assert "benchmark_duration_too_short" not in reasons


def test_malformed_fingerprint_is_rejected():
    record = build_run_record(tamper(load_valid_run(), hardware_fingerprint="sha256:zz"))
    assert "hardware_fingerprint_contradictory" in validate_submission_payload(record)


def test_artifact_hash_mismatch_is_rejected():
    payload = load_valid_run()
    payload["artifacts"][0]["declared_sha256"] = "0" * 64
    reasons = validate_submission_payload(build_run_record(payload))
    assert "artifact_hash_mismatch:runtime_stdout" in reasons
