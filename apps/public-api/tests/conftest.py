"""Shared fixtures for public-api tests.

Adds the fake-adapters package to the import path and provides a FastAPI test
client with every external dependency overridden by a fake adapter.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FAKE_ADAPTERS_ROOT = _REPO_ROOT / "packages" / "fake-adapters" / "src"
if str(_FAKE_ADAPTERS_ROOT) not in sys.path:
    sys.path.insert(0, str(_FAKE_ADAPTERS_ROOT))

from fake_artifact_vault import FakeArtifactVault
from fake_database import FakeDatabase
from fake_redis_queue import FakeRedisQueue

from src.dependencies.artifact_vault_provider import get_artifact_vault
from src.dependencies.database_session_provider import get_database_session
from src.dependencies.redis_queue_provider import get_benchmark_queue
from src.main import create_app


@pytest.fixture()
def database() -> FakeDatabase:
    return FakeDatabase()


def make_leaderboard_entry(**overrides) -> dict:
    entry = {
        "run_id": "run-lb-1",
        "gpu_model_id": "gpu-a",
        "model_release_id": "model-alpha",
        "quantization_profile_id": "q-gguf-q4-k-m",
        "quant_format": "gguf_q4",
        "runtime_engine": "llama_cpp",
        "context_tokens": 8192,
        "batch_size": 1,
        "decode_tok_s": 40.0,
        "prefill_tok_s": 800.0,
        "ttft_ms": 500.0,
        "peak_vram_mib": 20000.0,
        "power_watt_avg": 300.0,
        "quality_retention_estimate": 0.96,
        "trust_score": 0.8,
        "vram_capacity_mib": 24576,
        "submitted_at": "2026-08-01T00:00:00Z",
        "source_class": "measured_signed",
        "recipe_id": None,
        "seconds_per_clip": None,
        "it_per_s": None,
        "frames_per_s": None,
    }
    entry.update(overrides)
    return entry


# S26: leaderboard fixtures seed RUNS through the session API — the fake's
# leaderboard DERIVES from inserted rows (no canned entries anymore).
# Fictional fixture gpus map onto real seed rows with the same capacity the
# old canned entries claimed: gpu-a -> RTX 3090 (24576), gpu-b -> A6000 (49152).
_GPU_MAP = {"gpu-a": "gpu-rtx-3090", "gpu-b": "gpu-a6000"}
_RUNTIME_ID_BY_ENGINE = {
    "llama_cpp": "llama-cpp",
    "vllm": "vllm",
    "ollama": "ollama",
    "comfyui": "comfyui",
    "exllamav2": "exllamav2",
}


def seed_leaderboard_run(database, **overrides) -> str:
    """Insert the full run chain a derived leaderboard row needs; return run_id."""
    import uuid as _uuid

    entry = make_leaderboard_entry(**overrides)
    run_id = entry["run_id"]
    hardware_id = str(_uuid.uuid4())
    database.insert_hardware_submission(
        {
            "id": hardware_id,
            "owner_account_id": "00000000-0000-0000-0000-000000000001",
            "gpu_model_id": _GPU_MAP.get(entry["gpu_model_id"], entry["gpu_model_id"]),
            "cpu_model_id": None,
            "gpu_count": 1,
            "ram_gib": 32,
            "os_name": "seed",
            "os_version": "0",
            "environment_snapshot": {"hardware_fingerprint": "sha256:" + "0" * 64},
        }
    )
    scenario_id = str(_uuid.uuid4())
    database.insert_scenario(
        {
            "id": scenario_id,
            "scenario_kind": "prompt",
            "tensor_parallel": 1,
            "prompt_tokens": 512,
            "generated_tokens": 128,
            "context_tokens": entry["context_tokens"],
            "batch_size": entry["batch_size"],
            "width": None,
            "height": None,
            "frames": None,
            "steps": None,
            "cfg": None,
            "shift": None,
            "seed": None,
        }
    )
    database.insert_benchmark_run(
        {
            "id": run_id,
            "hardware_submission_id": hardware_id,
            "model_release_id": entry["model_release_id"],
            "quantization_profile_id": entry["quantization_profile_id"],
            "inference_runtime_id": _RUNTIME_ID_BY_ENGINE[entry["runtime_engine"]],
            "benchmark_scenario_id": scenario_id,
            "status": "validated",
            "client_version": "seed",
            "signature": "ff",
            "payload_digest": "sha256:" + "0" * 64,
            "signature_key_id": None,
            "recipe_id": entry["recipe_id"],
            "source_class": entry["source_class"],
            "seconds_per_clip": entry["seconds_per_clip"],
            "it_per_s": entry["it_per_s"],
            "frames_per_s": entry["frames_per_s"],
            "source_url": None,
        }
    )
    metric_units = {
        "decode_tok_s": "tok/s",
        "prefill_tok_s": "tok/s",
        "ttft_ms": "ms",
        "peak_vram_mib": "MiB",
        "power_watt_avg": "W",
    }
    for kind, unit in metric_units.items():
        value = entry[kind]
        if value is not None:
            database.insert_benchmark_metric(
                {
                    "benchmark_run_id": run_id,
                    "kind": kind,
                    "p50_value": float(value),
                    "unit": unit,
                }
            )
    if entry["submitted_at"]:
        database.set_run_submitted_at(run_id, entry["submitted_at"])
    if entry["trust_score"] is not None:
        database.set_run_trust_score(run_id, entry["trust_score"])
    return run_id


def seed_leaderboard_fixtures(database: FakeDatabase) -> FakeDatabase:
    seed_leaderboard_run(database)
    seed_leaderboard_run(
        database,
        run_id="run-lb-2",
        quantization_profile_id="q-fp16",
        quant_format="fp16",
        runtime_engine="vllm",
        context_tokens=16384,
        decode_tok_s=30.0,
        prefill_tok_s=1500.0,
        peak_vram_mib=23000.0,
        power_watt_avg=350.0,
        quality_retention_estimate=1.0,
        trust_score=0.7,
        submitted_at="2026-08-02T00:00:00Z",
    )
    seed_leaderboard_run(
        database,
        run_id="run-lb-3",
        gpu_model_id="gpu-b",
        model_release_id="model-beta",
        context_tokens=32768,
        decode_tok_s=90.0,
        prefill_tok_s=3000.0,
        peak_vram_mib=40000.0,
        power_watt_avg=400.0,
        trust_score=0.9,
        vram_capacity_mib=49152,
        submitted_at="2026-08-03T00:00:00Z",
    )
    seed_leaderboard_run(
        database,
        run_id="run-lb-4-infeasible",
        gpu_model_id="gpu-b",
        model_release_id="model-beta",
        quantization_profile_id="q-awq-int4",
        quant_format="awq",
        runtime_engine="ollama",
        context_tokens=4096,
        decode_tok_s=70.0,
        prefill_tok_s=2000.0,
        peak_vram_mib=60000.0,
        power_watt_avg=0.0,
        quality_retention_estimate=0.9775,
        trust_score=0.6,
        vram_capacity_mib=49152,
        submitted_at="2026-08-04T00:00:00Z",
    )
    return database


@pytest.fixture()
def seeded_database(database) -> FakeDatabase:
    return seed_leaderboard_fixtures(database)


@pytest.fixture()
def leaderboard_client(seeded_database, artifact_vault, benchmark_queue) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_database_session] = lambda: seeded_database
    app.dependency_overrides[get_artifact_vault] = lambda: artifact_vault
    app.dependency_overrides[get_benchmark_queue] = lambda: benchmark_queue
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def artifact_vault() -> FakeArtifactVault:
    return FakeArtifactVault()


@pytest.fixture()
def benchmark_queue() -> FakeRedisQueue:
    return FakeRedisQueue()


@pytest.fixture()
def client(database, artifact_vault, benchmark_queue) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_database_session] = lambda: database
    app.dependency_overrides[get_artifact_vault] = lambda: artifact_vault
    app.dependency_overrides[get_benchmark_queue] = lambda: benchmark_queue
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def trusted_key(monkeypatch, tmp_path) -> Ed25519PrivateKey:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_path = tmp_path / "trusted_public.pem"
    public_path.write_bytes(
        public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    monkeypatch.setenv("TRUSTED_ED25519_PUBLIC_KEY_PATH", str(public_path))
    return private_key


def sample_report_dict() -> dict:
    """A valid S01 0.9.0 report dict used across submission tests."""
    return {
        "schema_version": "0.9.0",
        "run_id": "01J9XYZTEST0000000000000001",
        "runtime": "llama_cpp",
        "runtime_version": "b4284",
        "hardware_fingerprint": "sha256:abcdef0123456789",
        "scenario": {
            "prompt_tokens": 4096,
            "generated_tokens": 512,
            "batch_size": 1,
            "context_tokens": 8192,
        },
        "metrics": {
            "ttft_ms": 812.0,
            "prefill_tok_s": 5041.0,
            "decode_tok_s": 18.7,
            "peak_vram_mib": 21811,
            "power_watt_avg": 412.0,
        },
        "artifacts": [
            {"artifact_kind": "runtime_stdout", "sha256": hashlib.sha256(b"stdout log").hexdigest()}
        ],
    }


def sign_report(private_key: Ed25519PrivateKey, report_dict: dict) -> tuple[str, str]:
    """Return (payload_digest, signature) for the canonicalized report."""
    canonical = json.dumps(report_dict, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    signature = private_key.sign(digest.encode("utf-8")).hex()
    return digest, signature


def make_passkey_session(client, database, monkeypatch, handle: str) -> str:
    """Drive the S13 ceremonies with patched WebAuthn; return a bearer token.

    Shared by S14/S15/S16 route tests so each file does not re-declare the
    patching boilerplate.
    """
    import base64
    from types import SimpleNamespace

    from src.services import authenticate_passkey, register_passkey

    credential_id = b"\x01" * 32
    raw_id = base64.urlsafe_b64encode(credential_id).decode().rstrip("=")

    monkeypatch.setattr(
        register_passkey,
        "_generate_registration_options",
        lambda *a, **k: SimpleNamespace(challenge=b"reg-challenge"),
    )
    monkeypatch.setattr(
        register_passkey,
        "_options_to_json",
        lambda o: '{"challenge": "%s"}'
        % base64.urlsafe_b64encode(o.challenge).decode().rstrip("="),
    )
    monkeypatch.setattr(
        register_passkey,
        "_verify_attestation",
        lambda *a, **k: SimpleNamespace(
            credential_id=credential_id, credential_public_key=b"cose-pubkey", sign_count=0
        ),
    )
    monkeypatch.setattr(
        authenticate_passkey,
        "_generate_authentication_options",
        lambda *a, **k: SimpleNamespace(challenge=b"login-challenge"),
    )
    monkeypatch.setattr(
        authenticate_passkey,
        "_options_to_json",
        lambda o: '{"challenge": "%s"}'
        % base64.urlsafe_b64encode(o.challenge).decode().rstrip("="),
    )
    monkeypatch.setattr(
        authenticate_passkey,
        "_verify_assertion",
        lambda *a, **k: SimpleNamespace(new_sign_count=5),
    )

    options = client.post("/v1/auth/passkey/register/options", json={"handle": handle}).json()
    client.post(
        "/v1/auth/passkey/register/verify",
        json={
            "handle": handle,
            "credential": {"response": {"challenge": options["options"]["challenge"]}},
        },
    )
    login_options = client.post("/v1/auth/passkey/login/options", json={"handle": handle}).json()
    login = client.post(
        "/v1/auth/passkey/login/verify",
        json={
            "handle": handle,
            "credential": {
                "rawId": raw_id,
                "response": {"challenge": login_options["options"]["challenge"]},
            },
        },
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]
