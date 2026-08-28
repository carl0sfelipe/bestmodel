"""Lightweight authenticated `reported` submissions (Story 5.2, FR-7).

Two entry points:

* :func:`register_contributor` — email-only account creation; the bearer token
  is returned once and only its sha256 is stored.
* :func:`submit_reported_run` — accepts community-reported numbers, quota-
  limited per source IP, and lands them as ``source_class='reported'`` with
  ``status='submitted'``. The leaderboard reads only ``status='validated'``
  rows, so a reported cell is out of the leaderboard by construction until a
  human review promotes it.

Honesty invariants (anti-fake-measurement): ``signature`` is the literal
``'reported'`` (there is no Ed25519 claim), ``payload_digest`` is the sha256
of the canonical request body (auditability, not authenticity), and the
contributor owns the derived hardware row instead of an anonymous owner.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import uuid
from typing import Any

from benchmark_scenario import BenchmarkScenario, VideoScenario
from pydantic import ValidationError

from src.dependencies.database_session_provider import DatabaseSession
from src.schemas.reported_submission_schema import (
    ContributorRegistration,
    ReportedSubmissionBody,
)

HARDWARE_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
DEFAULT_QUANTIZATION_PROFILE_ID = "q-fp16"
STATUS_SUBMITTED = "submitted"
SOURCE_CLASS_REPORTED = "reported"
SIGNATURE_REPORTED = "reported"
CLIENT_VERSION_REPORTED = "reported-submission-v1"
DEFAULT_QUOTA_PER_IP = 5
QUOTA_WINDOW_HOURS = 24

TOKEN_METRIC_UNITS = {
    "ttft_ms": "ms",
    "prefill_tok_s": "tok/s",
    "decode_tok_s": "tok/s",
    "peak_vram_mib": "MiB",
    "power_watt_avg": "W",
}
SCALAR_RUN_METRICS = ("seconds_per_clip", "it_per_s", "frames_per_s")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ReportedRejected(Exception):
    """Raised for 4xx reported-submission rejections carrying an HTTP status."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Contributor registration (the lightweight email "login")
# ---------------------------------------------------------------------------


def register_contributor(
    session: DatabaseSession, registration: ContributorRegistration
) -> tuple[int, dict[str, str]]:
    email = registration.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise ReportedRejected(400, "invalid email address")
    if session.find_contributor_by_email(email):
        raise ReportedRejected(409, f"email already registered: {email}")
    token = secrets.token_urlsafe(32)
    contributor_id = str(uuid.uuid4())
    session.insert_contributor(
        {
            "id": contributor_id,
            "email": email,
            "token_hash": hash_token(token),
        }
    )
    session.commit()
    return 201, {"contributor_id": contributor_id, "token": token}


def authenticate_contributor(
    session: DatabaseSession, authorization_header: str | None
) -> dict[str, Any]:
    """Resolve the bearer token to a contributor row; 401 on anything else."""
    if not authorization_header or not authorization_header.startswith("Bearer "):
        raise ReportedRejected(401, "missing bearer token; register at POST /v1/contributors")
    token = authorization_header[len("Bearer "):].strip()
    contributor = session.find_contributor_by_token_hash(hash_token(token))
    if contributor is None:
        raise ReportedRejected(401, "unknown contributor token")
    return contributor


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Reported submission
# ---------------------------------------------------------------------------


def submit_reported_run(
    session: DatabaseSession,
    body: ReportedSubmissionBody,
    contributor: dict[str, Any],
    client_ip: str,
) -> tuple[int, dict[str, str]]:
    scenario = _validate_scenario(body.scenario)
    model_release_id = _require_catalog_id(
        session.fetch_model_by_id(body.model_release_id),
        "model_release_id",
        body.model_release_id,
    )
    inference_runtime_id = _require_catalog_id(
        session.fetch_runtime_by_id(body.inference_runtime_id),
        "inference_runtime_id",
        body.inference_runtime_id,
    )
    quantization_profile_id = body.quantization_profile_id or DEFAULT_QUANTIZATION_PROFILE_ID
    _require_catalog_id(
        session.fetch_quantization_profile_by_id(quantization_profile_id),
        "quantization_profile_id",
        quantization_profile_id,
    )
    if body.gpu_model_id:
        _require_catalog_id(
            session.fetch_gpu_by_id(body.gpu_model_id), "gpu_model_id", body.gpu_model_id
        )
    if body.recipe_id:
        _require_catalog_id(session.fetch_recipe_by_id(body.recipe_id), "recipe_id", body.recipe_id)
    _require_at_least_one_metric(body.metrics)

    _enforce_quota(session, client_ip)

    hardware_submission_id = _reported_hardware_id(contributor, body.gpu_model_id)
    scenario_id = _scenario_id(scenario)
    existing = session.find_run_by_lookup(
        hardware_submission_id=hardware_submission_id,
        model_release_id=model_release_id,
        quantization_profile_id=quantization_profile_id,
        inference_runtime_id=inference_runtime_id,
        benchmark_scenario_id=scenario_id,
    )
    if existing:
        raise ReportedRejected(409, f"duplicate report; existing run id {existing['id']}")

    _ensure_reported_hardware(session, hardware_submission_id, contributor, body)
    session.insert_scenario(_scenario_record(scenario_id, scenario))
    run_id = str(uuid.uuid4())
    session.insert_benchmark_run(
        {
            "id": run_id,
            "hardware_submission_id": hardware_submission_id,
            "model_release_id": model_release_id,
            "quantization_profile_id": quantization_profile_id,
            "inference_runtime_id": inference_runtime_id,
            "benchmark_scenario_id": scenario_id,
            "status": STATUS_SUBMITTED,
            "client_version": CLIENT_VERSION_REPORTED,
            "signature": SIGNATURE_REPORTED,
            "payload_digest": _body_digest(body),
            "recipe_id": body.recipe_id,
            "source_class": SOURCE_CLASS_REPORTED,
            "seconds_per_clip": body.metrics.seconds_per_clip,
            "it_per_s": body.metrics.it_per_s,
            "frames_per_s": body.metrics.frames_per_s,
            "source_url": body.source_url,
        }
    )
    for kind, unit in TOKEN_METRIC_UNITS.items():
        value = getattr(body.metrics, kind)
        if value is not None:
            session.insert_benchmark_metric(
                {"benchmark_run_id": run_id, "kind": kind, "p50_value": float(value), "unit": unit}
            )
    session.insert_reported_submission_log(
        {
            "id": str(uuid.uuid4()),
            "contributor_id": contributor["id"],
            "benchmark_run_id": run_id,
            "ip_address": client_ip,
        }
    )
    session.commit()
    return 202, {"run_id": run_id}


def quota_per_ip() -> int:
    return int(os.environ.get("REPORTED_QUOTA_PER_IP", str(DEFAULT_QUOTA_PER_IP)))


def _enforce_quota(session: DatabaseSession, client_ip: str) -> None:
    recent = session.count_reported_submissions_since(client_ip, QUOTA_WINDOW_HOURS)
    if recent >= quota_per_ip():
        raise ReportedRejected(
            429,
            f"reported submission quota exceeded for this IP: {recent} in the last "
            f"{QUOTA_WINDOW_HOURS}h (limit {quota_per_ip()})",
        )


def _validate_scenario(raw: dict[str, Any]) -> BenchmarkScenario | VideoScenario:
    try:
        return VideoScenario(**raw)
    except ValidationError:
        pass
    try:
        return BenchmarkScenario(**raw)
    except ValidationError as exc:
        raise ReportedRejected(400, f"invalid scenario: {exc.errors()}") from exc


def _require_catalog_id(row: dict[str, Any] | None, field: str, value: str) -> str:
    if row is None:
        raise ReportedRejected(400, f"unknown {field}: {value}")
    return value


def _require_at_least_one_metric(metrics: Any) -> None:
    if all(getattr(metrics, name) is None for name in (*TOKEN_METRIC_UNITS, *SCALAR_RUN_METRICS)):
        raise ReportedRejected(400, "at least one metric must be reported")


def _reported_hardware_id(contributor: dict[str, Any], gpu_model_id: str | None) -> str:
    key = f"reported:{contributor['id']}|{gpu_model_id or 'unknown-gpu'}"
    return str(uuid.uuid5(HARDWARE_NAMESPACE, key))


def _ensure_reported_hardware(
    session: DatabaseSession,
    hardware_submission_id: str,
    contributor: dict[str, Any],
    body: ReportedSubmissionBody,
) -> None:
    if session.find_hardware_submission(hardware_submission_id):
        return
    session.insert_hardware_submission(
        {
            "id": hardware_submission_id,
            "owner_account_id": contributor["id"],
            "gpu_model_id": body.gpu_model_id,
            "cpu_model_id": None,
            "gpu_count": 1,
            "ram_gib": 1,
            "os_name": "reported",
            "os_version": "unverified",
            "environment_snapshot": {
                "source_class": SOURCE_CLASS_REPORTED,
                "note": body.note,
            },
        }
    )


def _scenario_id(scenario: BenchmarkScenario | VideoScenario) -> str:
    canonical = json.dumps(scenario.model_dump(), sort_keys=True, separators=(",", ":"))
    return str(uuid.uuid5(HARDWARE_NAMESPACE, canonical))


def _scenario_record(
    scenario_id: str, scenario: BenchmarkScenario | VideoScenario
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": scenario_id,
        "prompt_tokens": None,
        "generated_tokens": None,
        "context_tokens": None,
        "batch_size": None,
        "tensor_parallel": 1,
        "width": None,
        "height": None,
        "frames": None,
        "steps": None,
        "cfg": None,
        "shift": None,
        "seed": None,
    }
    if isinstance(scenario, VideoScenario):
        record["scenario_kind"] = "video"
    else:
        record["scenario_kind"] = "llm"
    record.update(scenario.model_dump())
    return record


def _body_digest(body: ReportedSubmissionBody) -> str:
    canonical = json.dumps(body.model_dump(), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
