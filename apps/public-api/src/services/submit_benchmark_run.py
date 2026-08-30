"""Benchmark submission intake pipeline (S09).

Validates the report against the S01 contract, checks the payload digest,
verifies the Ed25519 signature, verifies artifact digests, stores artifacts in
the vault, deduplicates on the benchmark_run lookup dimensions, inserts the run
and its metrics/artifacts, and pushes a queue event for the S10 worker.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from typing import Any, Iterable

from benchmark_report import BenchmarkReport
from benchmark_scenario import VideoScenario
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import ValidationError

from src.dependencies.artifact_vault_provider import ArtifactVault
from src.dependencies.database_session_provider import DatabaseSession
from src.dependencies.redis_queue_provider import BenchmarkQueue
from src.schemas.benchmark_submission_schema import SubmissionForm

HARDWARE_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
COMMUNITY_OWNER_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_QUANTIZATION_PROFILE_ID = "q-fp16"
STATUS_SUBMITTED = "submitted"
DIGEST_PREFIX = "sha256:"

# LOAD-BEARING (D4, AD-1): a metric kind absent here is SILENTLY DROPPED at
# insert — the run stores fine, the leaderboard never sees the number. Any
# new MetricKind in packages/domain-schema must land in this table, in the
# worker's evidence keys, and in the seed vocabulary, same commit.
METRIC_UNITS = {
    "ttft_ms": "ms",
    "prefill_tok_s": "tok/s",
    "decode_tok_s": "tok/s",
    "peak_vram_mib": "MiB",
    "power_watt_avg": "W",
}


class SubmissionRejected(Exception):
    """Raised for 400/409 intake rejections carrying an HTTP status code."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def submit_benchmark_run(
    session: DatabaseSession,
    vault: ArtifactVault,
    queue: BenchmarkQueue,
    form: SubmissionForm,
    artifact_files: Iterable[Any],
    caller_user: dict[str, Any] | None = None,
) -> tuple[int, dict[str, str]]:
    """Run the full intake pipeline; return the HTTP status and response body.

    ``caller_user`` is set when the upload carries a valid bearer token (S13
    agent/session tokens); anonymous uploads stay supported and are attributed
    to the community owner. A ``settle_claim_id`` form field links the run to
    one of the caller's open claims (S16); settlement itself completes in the
    intake worker once validation finishes.
    """
    report_dict = _parse_report_json(form.report)
    report = _validate_report(report_dict)
    _verify_payload_digest(report_dict, form.payload_digest)
    signature_key_id = _verify_signature(
        session, form.payload_digest, form.signature, form.signature_key_id, caller_user
    )
    artifact_records = _verify_and_store_artifacts(vault, report, artifact_files)
    hardware_submission_id = _hardware_submission_id(report)
    model_release_id = _resolve_model_release_id(session, form)
    quantization_profile_id = _resolve_quantization_profile_id(session, form)
    inference_runtime_id = _resolve_inference_runtime_id(session, form, report)
    scenario_id = _scenario_id(report)
    recipe_id = _resolve_recipe_id(session, form, report)
    _reject_if_duplicate(
        session,
        hardware_submission_id,
        model_release_id,
        quantization_profile_id,
        inference_runtime_id,
        scenario_id,
    )
    linked_claim = _resolve_settlement(session, form, caller_user, model_release_id)
    _ensure_hardware_submission(session, hardware_submission_id, report, caller_user)
    session.insert_scenario(_scenario_record(scenario_id, report))
    run_id = _insert_run(
        session,
        hardware_submission_id,
        model_release_id,
        quantization_profile_id,
        inference_runtime_id,
        scenario_id,
        form,
        report,
        recipe_id,
        signature_key_id,
    )
    _insert_metrics(session, run_id, report)
    _insert_artifacts(session, run_id, report, artifact_records)
    if linked_claim is not None:
        session.bind_claim_to_run(linked_claim["id"], run_id)
    session.commit()
    queue.publish(_queue_event(run_id, report))
    body = {"run_id": run_id}
    if linked_claim is not None:
        body["linked_claim_id"] = linked_claim["id"]
    return 202, body


def _resolve_settlement(
    session: DatabaseSession,
    form: SubmissionForm,
    caller_user: dict[str, Any] | None,
    resolved_model_release_id: str,
) -> dict[str, Any] | None:
    """Validate and return the open claim this run settles, if requested."""
    if not form.settle_claim_id:
        return None
    if caller_user is None:
        raise SubmissionRejected(401, "authentication is required to settle a claim")
    claim = session.find_run_claim_by_id(form.settle_claim_id)
    if claim is None:
        raise SubmissionRejected(404, f"claim not found: {form.settle_claim_id}")
    if claim["status"] != "open":
        raise SubmissionRejected(409, f"claim is not open (status: {claim['status']})")
    if claim["claimant_id"] != caller_user["id"]:
        raise SubmissionRejected(403, "only the claimant can settle a claim")
    if (
        claim.get("model_release_id")
        and resolved_model_release_id != claim["model_release_id"]
    ):
        raise SubmissionRejected(400, "run model does not match the claimed model")
    return claim


def _parse_report_json(report_json: str) -> dict[str, Any]:
    try:
        return json.loads(report_json)
    except json.JSONDecodeError as exc:
        raise SubmissionRejected(400, f"report is not valid JSON: {exc}") from exc


def _validate_report(report_dict: dict[str, Any]) -> BenchmarkReport:
    try:
        return BenchmarkReport(**report_dict)
    except ValidationError as exc:
        raise SubmissionRejected(400, f"report failed schema validation: {exc.errors()}") from exc


def _verify_payload_digest(report_dict: dict[str, Any], payload_digest: str) -> None:
    canonical = json.dumps(report_dict, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    submitted = _strip_digest_prefix(payload_digest)
    if not _digest_equal(expected, submitted):
        raise SubmissionRejected(400, "payload_digest does not match the canonicalized report")


def _verify_signature(
    session: DatabaseSession,
    payload_digest: str,
    signature: str,
    signature_key_id: str | None,
    caller_user: dict[str, Any] | None,
) -> str | None:
    """Verify the submission signature; return the key id that vouched for it.

    S23 two paths: with ``signature_key_id`` the signature is verified
    against the CALLER'S OWN registered ed25519 key (key of another user →
    403; revoked or missing key → 400) and the run is attributed to it.
    Without it, the legacy global trusted key path runs unchanged and the
    run stays unattributed (signature_key_id NULL).
    """
    if not signature_key_id:
        public_key = _load_trusted_public_key()
        try:
            public_key.verify(bytes.fromhex(signature), payload_digest.encode("utf-8"))
        except (InvalidSignature, ValueError) as exc:
            raise SubmissionRejected(400, "signature verification failed") from exc
        return None

    key_record = session.fetch_signing_key_by_id(signature_key_id)
    if key_record is None:
        raise SubmissionRejected(400, "signing key not found")
    if caller_user is None or key_record["app_user_id"] != caller_user["id"]:
        raise SubmissionRejected(403, "signing key belongs to another user")
    if key_record.get("revoked_at") is not None:
        raise SubmissionRejected(400, "signing key has been revoked")
    public_key = _load_pem_ed25519(key_record["public_key_pem"])
    try:
        public_key.verify(bytes.fromhex(signature), payload_digest.encode("utf-8"))
    except (InvalidSignature, ValueError) as exc:
        raise SubmissionRejected(400, "signature verification failed") from exc
    return signature_key_id


def _load_pem_ed25519(public_key_pem: str) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise SubmissionRejected(400, "registered public key is unreadable") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise SubmissionRejected(400, "registered public key is not ed25519")
    return key


def _load_trusted_public_key() -> Ed25519PublicKey:
    path = os.environ.get("TRUSTED_ED25519_PUBLIC_KEY_PATH")
    if not path:
        raise SubmissionRejected(400, "TRUSTED_ED25519_PUBLIC_KEY_PATH is not configured")
    try:
        with open(path, "rb") as handle:
            key = serialization.load_pem_public_key(handle.read())
    except (OSError, ValueError) as exc:
        raise SubmissionRejected(400, f"unable to load trusted public key: {exc}") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise SubmissionRejected(400, "trusted public key is not an Ed25519 key")
    return key


def _verify_and_store_artifacts(
    vault: ArtifactVault, report: BenchmarkReport, artifact_files: Iterable[Any]
) -> list[tuple[Any, str, int]]:
    files = list(artifact_files)
    if len(files) != len(report.artifacts):
        raise SubmissionRejected(400, f"expected {len(report.artifacts)} artifacts, received {len(files)}")
    records = []
    for index, (artifact, upload) in enumerate(zip(report.artifacts, files)):
        data = upload.file.read()
        digest = hashlib.sha256(data).hexdigest()
        if not _digest_equal(_strip_digest_prefix(artifact.sha256), digest):
            raise SubmissionRejected(
                400, f"artifact_{index} digest does not match report.artifacts[{index}].sha256"
            )
        storage_key = f"{report.run_id}/artifact_{index}"
        vault.store(storage_key, data)
        records.append((artifact, storage_key, len(data)))
    return records


def _hardware_submission_id(report: BenchmarkReport) -> str:
    return str(uuid.uuid5(HARDWARE_NAMESPACE, report.hardware_fingerprint))


def _scenario_id(report: BenchmarkReport) -> str:
    canonical = json.dumps(report.scenario.model_dump(), sort_keys=True, separators=(",", ":"))
    return str(uuid.uuid5(HARDWARE_NAMESPACE, canonical))


def _resolve_model_release_id(session: DatabaseSession, form: SubmissionForm) -> str:
    """Resolve the model binding.

    The 0.9.0 report does not carry a model_release binding. Phase 0 uses the
    optional form override or falls back to the first catalog model
    deterministically; S10 binds runs from parsed evidence.
    """
    if form.model_release_id:
        if not session.fetch_model_by_id(form.model_release_id):
            raise SubmissionRejected(400, f"unknown model_release_id: {form.model_release_id}")
        return form.model_release_id
    return session.fetch_first_model_release_id()


def _resolve_quantization_profile_id(session: DatabaseSession, form: SubmissionForm) -> str:
    """Resolve the quantization binding, defaulting to fp16 (no quantization)."""
    profile_id = form.quantization_profile_id or DEFAULT_QUANTIZATION_PROFILE_ID
    if not session.fetch_quantization_profile_by_id(profile_id):
        raise SubmissionRejected(400, f"unknown quantization_profile_id: {profile_id}")
    return profile_id


def _resolve_inference_runtime_id(
    session: DatabaseSession, form: SubmissionForm, report: BenchmarkReport
) -> str:
    """Resolve the runtime binding from the report engine via a catalog lookup."""
    if form.inference_runtime_id:
        if not session.fetch_runtime_by_id(form.inference_runtime_id):
            raise SubmissionRejected(400, f"unknown inference_runtime_id: {form.inference_runtime_id}")
        return form.inference_runtime_id
    runtime_row = session.fetch_runtime_by_engine(report.runtime.value)
    if not runtime_row:
        raise SubmissionRejected(400, f"no registered runtime for engine {report.runtime.value}")
    return runtime_row["id"]


def _reject_if_duplicate(
    session: DatabaseSession,
    hardware_submission_id: str,
    model_release_id: str,
    quantization_profile_id: str,
    inference_runtime_id: str,
    benchmark_scenario_id: str,
) -> None:
    existing = session.find_run_by_lookup(
        hardware_submission_id=hardware_submission_id,
        model_release_id=model_release_id,
        quantization_profile_id=quantization_profile_id,
        inference_runtime_id=inference_runtime_id,
        benchmark_scenario_id=benchmark_scenario_id,
    )
    if existing:
        raise SubmissionRejected(409, f"duplicate submission; existing run id {existing['id']}")


def _ensure_hardware_submission(
    session: DatabaseSession,
    hardware_submission_id: str,
    report: BenchmarkReport,
    caller_user: dict[str, Any] | None = None,
) -> None:
    """Create the community-owned hardware row derived from the fingerprint.

    ``benchmark_run.hardware_submission_id`` is a NOT NULL FK and Phase 0 has
    no account registration, so the id is derived deterministically from the
    hardware fingerprint (uuid5) and an anonymous owner row is created once.
    """
    if session.find_hardware_submission(hardware_submission_id):
        return
    session.insert_hardware_submission(
        {
            "id": hardware_submission_id,
            "owner_account_id": caller_user["id"] if caller_user else COMMUNITY_OWNER_ID,
            "gpu_model_id": None,
            "cpu_model_id": None,
            "gpu_count": 1,
            "ram_gib": 1,
            "os_name": "unknown",
            "os_version": "unknown",
            "environment_snapshot": {"hardware_fingerprint": report.hardware_fingerprint},
        }
    )


def _resolve_recipe_id(
    session: DatabaseSession, form: SubmissionForm, report: BenchmarkReport
) -> str | None:
    """Resolve the recipe binding for video runs (Épico 1, Story 1.3).

    The signed report wins over the form override; an unknown recipe id is a
    400 so mis-typed ids never silently land as NULL.
    """
    recipe_id = report.recipe_id or form.recipe_id
    if not recipe_id:
        return None
    if not session.fetch_recipe_by_id(recipe_id):
        raise SubmissionRejected(400, f"unknown recipe_id: {recipe_id}")
    return recipe_id


def _scenario_record(scenario_id: str, report: BenchmarkReport) -> dict[str, Any]:
    scenario = report.scenario
    if isinstance(scenario, VideoScenario):
        return {
            "id": scenario_id,
            "scenario_kind": "video",
            "prompt_tokens": None,
            "generated_tokens": None,
            "context_tokens": None,
            "batch_size": None,
            "tensor_parallel": 1,
            "width": scenario.width,
            "height": scenario.height,
            "frames": scenario.frames,
            "steps": scenario.steps,
            "cfg": scenario.cfg,
            "shift": scenario.shift,
            "seed": scenario.seed,
        }
    return {
        "id": scenario_id,
        "scenario_kind": "llm",
        "prompt_tokens": report.scenario.prompt_tokens,
        "generated_tokens": report.scenario.generated_tokens,
        "context_tokens": report.scenario.context_tokens,
        "batch_size": report.scenario.batch_size,
        "tensor_parallel": 1,
        "width": None,
        "height": None,
        "frames": None,
        "steps": None,
        "cfg": None,
        "shift": None,
        "seed": None,
    }

def _insert_run(
    session: DatabaseSession,
    hardware_submission_id: str,
    model_release_id: str,
    quantization_profile_id: str,
    inference_runtime_id: str,
    benchmark_scenario_id: str,
    form: SubmissionForm,
    report: BenchmarkReport,
    recipe_id: str | None,
    signature_key_id: str | None,
) -> str:
    run_id = str(uuid.uuid4())
    session.insert_benchmark_run(
        {
            "id": run_id,
            "hardware_submission_id": hardware_submission_id,
            "model_release_id": model_release_id,
            "quantization_profile_id": quantization_profile_id,
            "inference_runtime_id": inference_runtime_id,
            "benchmark_scenario_id": benchmark_scenario_id,
            "status": STATUS_SUBMITTED,
            "client_version": form.client_version,
            "signature": form.signature,
            "payload_digest": form.payload_digest,
            "signature_key_id": signature_key_id,
            "recipe_id": recipe_id,
            "source_class": "measured_signed",
            "seconds_per_clip": report.metrics.seconds_per_clip,
            "it_per_s": report.metrics.it_per_s,
            "frames_per_s": report.metrics.frames_per_s,
            "source_url": None,
        }
    )
    return run_id


def _insert_metrics(session: DatabaseSession, run_id: str, report: BenchmarkReport) -> None:
    for kind, value in report.metrics.model_dump().items():
        if kind not in METRIC_UNITS or value is None:
            continue
        session.insert_benchmark_metric(
            {
                "benchmark_run_id": run_id,
                "kind": kind,
                "p50_value": float(value),
                "unit": METRIC_UNITS[kind],
            }
        )


def _insert_artifacts(
    session: DatabaseSession,
    run_id: str,
    report: BenchmarkReport,
    artifact_records: list[tuple[Any, str, int]],
) -> None:
    for artifact, storage_key, size_bytes in artifact_records:
        session.insert_benchmark_artifact(
            {
                "id": str(uuid.uuid4()),
                "benchmark_run_id": run_id,
                "artifact_kind": artifact.artifact_kind.value,
                "sha256_digest": _strip_digest_prefix(artifact.sha256),
                "storage_key": storage_key,
                "size_bytes": size_bytes,
            }
        )


def _queue_event(run_id: str, report: BenchmarkReport) -> dict[str, str]:
    return {
        "event": "benchmark_run.submitted",
        "run_id": run_id,
        "schema_version": report.schema_version,
        "hardware_fingerprint": report.hardware_fingerprint,
    }


def _strip_digest_prefix(value: str) -> str:
    return value[len(DIGEST_PREFIX):] if value.startswith(DIGEST_PREFIX) else value


def _digest_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
