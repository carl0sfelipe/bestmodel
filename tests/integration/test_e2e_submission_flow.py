"""End-to-end submission flow: CLI-style signed report -> intake API -> worker
validation -> leaderboard visibility, using fake adapters (no external services).
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fake_artifact_vault import FakeArtifactVault
from fake_database import FakeDatabase
from fake_redis_queue import FakeRedisQueue
from src.dependencies.database_session_provider import get_database_session
from src.dependencies.artifact_vault_provider import get_artifact_vault
from src.dependencies.redis_queue_provider import get_benchmark_queue
from src.schemas.benchmark_submission_schema import SubmissionForm
from src.services.submit_benchmark_run import submit_benchmark_run
from src.main import create_app
from src.services.query_leaderboard import query_leaderboard
from worker import STATUS_VALIDATED, process_run

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEED_DIR = _REPO_ROOT / "infra" / "seed"


class _FakeUpload:
    def __init__(self, data: bytes) -> None:
        self.file = io.BytesIO(data)


class _WorkerRepository:
    def __init__(self) -> None:
        self.statuses: dict[str, tuple[str, float]] = {}
        self.assessments: dict[str, dict] = {}
        self.ranking_updates: list[dict] = []

    def find_existing_run_in_group(self, dimension, exclude_run_id, statuses):
        return False

    def fetch_peer_decode_values(self, dimension, exclude_run_id):
        return []

    def count_peers(self, dimension):
        return 0

    def record_trust_assessment(self, run_id, assessment):
        self.assessments[run_id] = assessment

    def set_run_status(self, run_id, status, trust_score):
        self.statuses[run_id] = (status, trust_score)

    def publish_ranking_update(self, event):
        self.ranking_updates.append(event)

    def fetch_run_payload(self, run_id):
        return None


def _seed_row(filename: str, record_id: str) -> dict:
    rows = json.loads((_SEED_DIR / filename).read_text(encoding="utf-8"))
    return next(row for row in rows if row["id"] == record_id)


def _build_signed_submission(private_key: Ed25519PrivateKey) -> tuple[dict, str, str, str]:
    metrics = {
        "ttft_ms": 819.2,
        "prefill_tok_s": 5000.0,
        "decode_tok_s": 18.7,
        "peak_vram_mib": 21811,
        "power_watt_avg": 0.0,
    }
    evidence = (
        "metric ttft_ms 819.200\nmetric prefill_tok_s 5000.000\n"
        "metric decode_tok_s 18.700\nmetric peak_vram_mib 21811\nmetric power_watt_avg 0.0\n"
    )
    report = {
        "schema_version": "0.9.0",
        "run_id": "e2e-gate-run-0001",
        "runtime": "llama_cpp",
        "runtime_version": "b4568",
        "hardware_fingerprint": "sha256:" + "ab" * 32,
        "scenario": {
            "prompt_tokens": 24,
            "generated_tokens": 512,
            "batch_size": 1,
            "context_tokens": 8192,
        },
        "metrics": metrics,
        "artifacts": [
            {
                "artifact_kind": "runtime_stdout",
                "sha256": hashlib.sha256(evidence.encode()).hexdigest(),
            }
        ],
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    digest = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    signature = private_key.sign(digest.encode()).hex()
    return report, digest, signature, evidence


@pytest.fixture()
def trusted_key(monkeypatch, tmp_path) -> Ed25519PrivateKey:
    private_key = Ed25519PrivateKey.generate()
    public_path = tmp_path / "trusted_public.pem"
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    monkeypatch.setenv("TRUSTED_ED25519_PUBLIC_KEY_PATH", str(public_path))
    return private_key


@pytest.fixture()
def intake_stack():
    database = FakeDatabase()
    vault = FakeArtifactVault()
    queue = FakeRedisQueue()
    return database, vault, queue


def test_signed_submission_is_accepted_and_enqueued(intake_stack, trusted_key):
    database, vault, queue = intake_stack
    report, digest, signature, evidence = _build_signed_submission(trusted_key)
    form = SubmissionForm(
        report=json.dumps(report),
        signature=signature,
        payload_digest=digest,
        challenge_nonce="nonce-e2e",
        client_version="gate-test",
        model_release_id="model-qwq-32b",
        quantization_profile_id="q-gguf-q4-k-m",
        inference_runtime_id="llama-cpp",
    )
    status, body = submit_benchmark_run(
        database, vault, queue, form, [_FakeUpload(evidence.encode())]
    )
    assert status == 202
    assert body["run_id"]


def test_worker_validates_the_accepted_run(intake_stack, trusted_key):
    database, vault, queue = intake_stack
    report, digest, signature, evidence = _build_signed_submission(trusted_key)
    form = SubmissionForm(
        report=json.dumps(report),
        signature=signature,
        payload_digest=digest,
        challenge_nonce="nonce-e2e",
        client_version="gate-test",
        model_release_id="model-qwq-32b",
        quantization_profile_id="q-gguf-q4-k-m",
        inference_runtime_id="llama-cpp",
    )
    status, body = submit_benchmark_run(
        database, vault, queue, form, [_FakeUpload(evidence.encode())]
    )
    assert status == 202

    payload = {
        **report,
        "run_id": body["run_id"],
        "runtime_engine": "llama_cpp",
        "signature_valid": True,
        "duration_seconds": 819.2 / 1000.0 + 512 / 18.7,
        "hardware": _seed_row("gpu_models.json", "gpu-rtx-3090"),
        "model": _seed_row("model_releases.json", "model-qwq-32b"),
        "quant": _seed_row("quantization_profiles.json", "q-gguf-q4-k-m"),
        "dimension": {
            "hardware_model_id": "gpu-rtx-3090",
            "model_release_id": "model-qwq-32b",
            "quantization_profile_id": "q-gguf-q4-k-m",
            "runtime_engine": "llama_cpp",
            "context_tokens": 8192,
            "batch_size": 1,
        },
        "artifacts": [
            {
                "artifact_kind": "runtime_stdout",
                "declared_sha256": hashlib.sha256(evidence.encode()).hexdigest(),
                "content": evidence,
            }
        ],
    }
    repository = _WorkerRepository()
    outcome = process_run(payload, repository)
    assert outcome["status"] == STATUS_VALIDATED
    assert outcome["outlier_flags"] == []
    assert repository.statuses[body["run_id"]][0] == STATUS_VALIDATED
    assert repository.ranking_updates[-1]["run_id"] == body["run_id"]


def test_validated_run_appears_on_leaderboard(intake_stack):
    database, _vault, _queue = intake_stack
    database.add_leaderboard_entry(
        {
            "run_id": "e2e-gate-run-0001",
            "gpu_model_id": "gpu-rtx-3090",
            "model_release_id": "model-qwq-32b",
            "quantization_profile_id": "q-gguf-q4-k-m",
            "quant_format": "gguf_q4",
            "runtime_engine": "llama_cpp",
            "context_tokens": 8192,
            "batch_size": 1,
            "decode_tok_s": 18.7,
            "prefill_tok_s": 5000.0,
            "ttft_ms": 819.2,
            "peak_vram_mib": 21811.0,
            "power_watt_avg": 0.0,
            "quality_retention_estimate": 0.96,
            "trust_score": 0.8,
            "vram_capacity_mib": 24576,
            "submitted_at": "2026-08-04T00:00:00Z",
        }
    )
    outcome = query_leaderboard(database, {}, None, None, None)
    assert [run["run_id"] for run in outcome["runs"]] == ["e2e-gate-run-0001"]
    assert outcome["runs"][0]["rank_score"] >= 0.0


def test_api_app_wires_all_providers(intake_stack):
    database, vault, queue = intake_stack
    app = create_app()
    app.dependency_overrides[get_database_session] = lambda: database
    app.dependency_overrides[get_artifact_vault] = lambda: vault
    app.dependency_overrides[get_benchmark_queue] = lambda: queue
    assert app.routes
