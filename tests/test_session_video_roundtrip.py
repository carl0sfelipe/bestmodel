"""S25a-rt: video round-trip through the session API on BOTH backends.

Writes a video benchmark_scenario + benchmark_run via the session API and reads
both back via find_scenario_by_id / find_run_by_id, asserting field-set
completeness generated from the domain-schema run_record models (never a
hand-maintained list) and value equality for the video scalars, source_class
and recipe_id.

Backends: FakeDatabase always (``make test``). PostgresSession when
DATABASE_URL is set and reachable — that leg runs inside ``make gate``, which
exports DATABASE_URL against the migrated+seeded dev database; it uses one
connection wrapped in a transaction that is rolled back on teardown, so no
rows survive the test.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from typing import Any, Iterator

import pytest

from fake_database import FakeDatabase
from run_record import BenchmarkRunRecord, BenchmarkScenarioRecord
from src.dependencies.database_session_provider import DatabaseSession, PostgresSession

RECIPE_ID = "wan22-flf2v-720p-81f-v1"
MODEL_RELEASE_ID = "model-wan22-i2v-flf2v-14b"
QUANTIZATION_PROFILE_ID = "q-fp16"
RUNTIME_ID = "comfyui"
COMMUNITY_OWNER_ID = "00000000-0000-0000-0000-000000000001"
# Binary-exact in float4/REAL so Postgres round-trips them bit-identical.
SECONDS_PER_CLIP = 12.5
IT_PER_S = 1.625
FRAMES_PER_S = 6.5


def _video_records() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    hardware_id = str(uuid.uuid4())
    scenario_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    hardware = {
        "id": hardware_id,
        "owner_account_id": COMMUNITY_OWNER_ID,
        "gpu_model_id": None,
        "cpu_model_id": None,
        "gpu_count": 1,
        "ram_gib": 1,
        "os_name": "s25rt",
        "os_version": "0",
        "environment_snapshot": {"hardware_fingerprint": "sha256:" + "0" * 64},
    }
    scenario = {
        "id": scenario_id,
        "scenario_kind": "video",
        "prompt_tokens": None,
        "generated_tokens": None,
        "context_tokens": None,
        "batch_size": None,
        "tensor_parallel": 1,
        "width": 1280,
        "height": 720,
        "frames": 81,
        "steps": 20,
        "cfg": 3.5,
        "shift": 5.0,
        "seed": 42,
    }
    run = {
        "id": run_id,
        "hardware_submission_id": hardware_id,
        "model_release_id": MODEL_RELEASE_ID,
        "quantization_profile_id": QUANTIZATION_PROFILE_ID,
        "inference_runtime_id": RUNTIME_ID,
        "benchmark_scenario_id": scenario_id,
        "status": "submitted",
        "client_version": "s25-roundtrip",
        "signature": "sig-s25",
        "payload_digest": "sha256:" + "0" * 64,
        "signature_key_id": None,
        "recipe_id": RECIPE_ID,
        "source_class": "measured_signed",
        "seconds_per_clip": SECONDS_PER_CLIP,
        "it_per_s": IT_PER_S,
        "frames_per_s": FRAMES_PER_S,
        "source_url": None,
    }
    return hardware, scenario, run


def _assert_roundtrip(session: DatabaseSession) -> None:
    hardware, scenario, run = _video_records()
    # The written field-set IS the domain model's — the drift killer (D3.3):
    # a model field missing from either dict fails here by name.
    assert set(scenario) == set(BenchmarkScenarioRecord.model_fields)
    assert set(run) == set(BenchmarkRunRecord.model_fields)

    session.insert_hardware_submission(hardware)
    session.insert_scenario(scenario)
    session.insert_benchmark_run(run)

    read_scenario = session.find_scenario_by_id(scenario["id"])
    read_run = session.find_run_by_id(run["id"])
    assert read_scenario is not None, "scenario row vanished on read-back"
    assert read_run is not None, "run row vanished on read-back"

    # Field-set completeness of the read-back rows.
    assert set(BenchmarkScenarioRecord.model_fields) <= set(read_scenario)
    assert set(BenchmarkRunRecord.model_fields) <= set(read_run)

    for field in BenchmarkScenarioRecord.model_fields:
        _assert_field(field, scenario, read_scenario)
    for field in BenchmarkRunRecord.model_fields:
        _assert_field(field, run, read_run)

    # The S25a-rt oracle, named: video identity + scalars survive the backend.
    assert read_run["source_class"] == "measured_signed"
    assert read_run["recipe_id"] == RECIPE_ID
    assert read_run["seconds_per_clip"] == SECONDS_PER_CLIP
    assert read_run["it_per_s"] == IT_PER_S
    assert read_run["frames_per_s"] == FRAMES_PER_S


def _assert_field(field: str, written: dict[str, Any], read_back: dict[str, Any]) -> None:
    expected = written[field]
    got = read_back[field]
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert isinstance(got, (int, float, Decimal)), f"{field}: {got!r} not numeric"
        assert float(got) == float(expected), f"{field}: {got!r} != {expected!r}"
    else:
        assert str(got) == str(expected), f"{field}: {got!r} != {expected!r}"


def test_video_roundtrip_fake_database() -> None:
    _assert_roundtrip(FakeDatabase())


@pytest.fixture()
def postgres_session() -> Iterator[DatabaseSession]:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL not set — Postgres leg runs inside make gate")
    import psycopg
    from psycopg.rows import dict_row

    try:
        connection = psycopg.connect(dsn, row_factory=dict_row)
    except Exception as exc:  # unreachable DB is an environment gap, not a bug
        pytest.skip(f"DATABASE_URL unreachable ({exc})")
    session = PostgresSession(connection)
    try:
        yield session
    finally:
        # One transaction, rolled back: the round-trip proves itself without
        # leaving rows behind.
        connection.rollback()
        session.close()


def test_video_roundtrip_postgres(postgres_session: DatabaseSession) -> None:
    _assert_roundtrip(postgres_session)
