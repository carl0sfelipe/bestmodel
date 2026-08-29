"""Payload-level validation for the anti-fraud rules of plan section 12.6.

Returns a list of rejection reasons; an empty list means the payload passes.
Roofline and memory plausibility are handled by their own modules (section 12.3)
and duplicate detection by ``detect_duplicate_submission`` (section 12.4).
"""

from __future__ import annotations

import hashlib

from worker_models import SUPPORTED_SCHEMA_VERSION, RunRecord, scenario_is_video

DURATION_FLOOR_SECONDS = 1.0
DURATION_CONSISTENCY_FRACTION = 0.5
FINGERPRINT_PREFIX = "sha256:"


def validate_submission_payload(record: RunRecord) -> list[str]:
    reasons: list[str] = []
    if not record.signature_valid:
        reasons.append("invalid_signature")
    if record.schema_version != SUPPORTED_SCHEMA_VERSION:
        reasons.append("unsupported_schema_version")
    if record.runtime_version is None or record.runtime_version == "":
        reasons.append("missing_runtime_version")
    if not _fingerprint_well_formed(record.hardware_fingerprint):
        reasons.append("hardware_fingerprint_contradictory")
    if not _duration_plausible(record):
        reasons.append("benchmark_duration_too_short")
    reasons.extend(_artifact_hash_mismatches(record))
    return reasons


def _duration_plausible(record: RunRecord) -> bool:
    """A run must last at least a small floor AND be consistent with its own
    reported throughput: faking a high tok/s with a short duration is what the
    check targets, so the bound scales with generated_tokens / decode_tok_s.
    Video runs are checked the same way against frames / frames_per_s."""
    floor = DURATION_FLOOR_SECONDS
    if scenario_is_video(record):
        frames_per_s = record.metrics.get("frames_per_s", 0.0)
        if frames_per_s > 0:
            expected_seconds = record.scenario["frames"] / frames_per_s
            floor = max(floor, DURATION_CONSISTENCY_FRACTION * expected_seconds)
        return record.duration_seconds >= floor
    decode_tok_s = record.metrics.get("decode_tok_s", 0.0)
    if decode_tok_s > 0:
        expected_seconds = record.scenario["generated_tokens"] / decode_tok_s
        floor = max(floor, DURATION_CONSISTENCY_FRACTION * expected_seconds)
    return record.duration_seconds >= floor


def _fingerprint_well_formed(fingerprint: str) -> bool:
    if not fingerprint.startswith(FINGERPRINT_PREFIX):
        return False
    digest = fingerprint[len(FINGERPRINT_PREFIX):]
    if len(digest) != 64:
        return False
    return all(char in "0123456789abcdef" for char in digest)


def _artifact_hash_mismatches(record: RunRecord) -> list[str]:
    reasons: list[str] = []
    for artifact in record.artifacts:
        actual = hashlib.sha256(artifact.content.encode("utf-8")).hexdigest()
        if actual != artifact.declared_sha256.lower():
            reasons.append(f"artifact_hash_mismatch:{artifact.artifact_kind}")
    return reasons
