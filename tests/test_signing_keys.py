"""S23 session contract: per-user signing keys on BOTH backends.

The S25a introspection test already fails if a backend misses a method;
this file pins the BEHAVIOR: insert/fetch/list/revoke and the run_count
attribution derived from runs carrying ``signature_key_id``.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest

from fake_database import FakeDatabase
from src.dependencies.database_session_provider import DatabaseSession, PostgresSession


def _pem() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _key_record(app_user_id: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "id": str(uuid.uuid4()),
        "app_user_id": app_user_id,
        "label": "rig-key",
        "public_key_pem": _pem(),
        "algorithm": "ed25519",
        "created_at": "2026-08-30T00:00:00+00:00",
        "revoked_at": None,
    }
    record.update(overrides)
    return record


# Seeded catalog ids (same ones the S25a-rt round-trip relies on): the
# Postgres leg enforces every benchmark_run FK, so runs reference real rows.
SEEDED_MODEL_RELEASE_ID = "model-wan22-i2v-flf2v-14b"
SEEDED_QUANTIZATION_PROFILE_ID = "q-fp16"
SEEDED_RUNTIME_ID = "comfyui"


def _run_record(signature_key_id: str | None, hardware_id: str, scenario_id: str) -> dict[str, Any]:
    from run_record import BenchmarkRunRecord

    base = {
        "id": str(uuid.uuid4()),
        "hardware_submission_id": hardware_id,
        "model_release_id": SEEDED_MODEL_RELEASE_ID,
        "quantization_profile_id": SEEDED_QUANTIZATION_PROFILE_ID,
        "inference_runtime_id": SEEDED_RUNTIME_ID,
        "benchmark_scenario_id": scenario_id,
        "status": "submitted",
        "client_version": "s23-test",
        "signature": "ff",
        "payload_digest": "sha256:" + "0" * 64,
        "signature_key_id": signature_key_id,
        "recipe_id": None,
        "source_class": "measured_signed",
        "seconds_per_clip": None,
        "it_per_s": None,
        "frames_per_s": None,
        "source_url": None,
    }
    BenchmarkRunRecord.model_validate(base)
    return base


def _assert_session_contract(session: DatabaseSession) -> None:
    user_id = str(uuid.uuid4())
    session.insert_app_user(
        {"id": user_id, "handle": f"s23-{user_id[:8]}", "display_name": "S23"}
    )
    other_user_id = str(uuid.uuid4())
    session.insert_app_user(
        {"id": other_user_id, "handle": f"s23o-{other_user_id[:8]}", "display_name": "S23O"}
    )

    key = _key_record(user_id)
    session.insert_signing_key(key)

    # psycopg returns UUID columns as UUID objects (fake returns str):
    # compare across the boundary with str(), the round-trip house pattern.
    fetched = session.fetch_signing_key_by_id(key["id"])
    assert fetched is not None and str(fetched["app_user_id"]) == user_id

    listed = session.fetch_signing_keys_by_user(user_id)
    # str() on ids: psycopg hands back UUID objects, the fake hands back str
    assert [str(row["id"]) for row in listed] == [key["id"]]
    assert int(listed[0].get("run_count") or 0) == 0
    assert session.fetch_signing_keys_by_user(other_user_id) == []

    # attribution: a run carrying the key id counts toward it. Postgres
    # enforces the benchmark_run -> hardware_submission FK, so each run
    # gets its own hardware row first (the fake has no constraints, but
    # the contract test must pass on BOTH backends with the same steps).
    for key_id in (key["id"], None):
        hardware = {
            "id": str(uuid.uuid4()),
            "owner_account_id": "00000000-0000-0000-0000-000000000001",
            "gpu_model_id": None,
            "cpu_model_id": None,
            "gpu_count": 1,
            "ram_gib": 1,
            "os_name": "s23rt",
            "os_version": "0",
            "environment_snapshot": {"hardware_fingerprint": "sha256:" + "0" * 64},
        }
        session.insert_hardware_submission(hardware)
        scenario = {
            "id": str(uuid.uuid4()),
            "scenario_kind": "prompt",
            "tensor_parallel": 1,
            "prompt_tokens": 128,
            "generated_tokens": 32,
            "context_tokens": 160,
            "batch_size": 1,
            "width": None,
            "height": None,
            "frames": None,
            "steps": None,
            "cfg": None,
            "shift": None,
            "seed": None,
        }
        session.insert_scenario(scenario)
        session.insert_benchmark_run(_run_record(key_id, hardware["id"], scenario["id"]))
    listed = session.fetch_signing_keys_by_user(user_id)
    assert int(listed[0]["run_count"]) == 1  # only the attributed run counts

    # revoke is visible on fetch
    session.revoke_signing_key(key["id"], "2026-08-30T01:00:00+00:00")
    fetched = session.fetch_signing_key_by_id(key["id"])
    assert fetched is not None and fetched["revoked_at"] is not None


def test_signing_keys_fake_database() -> None:
    _assert_session_contract(FakeDatabase())


@pytest.fixture()
def postgres_session():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL not set — Postgres leg runs inside make gate")
    import psycopg
    from psycopg.rows import dict_row

    try:
        connection = psycopg.connect(dsn, row_factory=dict_row)
    except Exception as exc:  # environment gap, not a bug
        pytest.skip(f"DATABASE_URL unreachable ({exc})")
    session = PostgresSession(connection)
    try:
        yield session
    finally:
        connection.rollback()
        session.close()


def test_signing_keys_postgres(postgres_session: DatabaseSession) -> None:
    _assert_session_contract(postgres_session)
