"""Tests for the deterministic harvester (Story 4.1).

Expected cell ids are recomputed here from the documented uuid5 recipe, so
this file independently guards the staging contract (never production,
unverified, byte-stable reruns) against accidental drift.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest

from harvester import SourceMutated, harvest

FIXTURE = Path(__file__).parent / "fixtures" / "model-card-fixture.json"
SOURCE_URL = "https://huggingface.co/example/model-card-fixture"
NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_cell_id(
    fixture_sha256: str, gpu: str, model: str, recipe: str | None, metric: str
) -> str:
    recipe_key = recipe if recipe is not None else ""
    key = f"{SOURCE_URL}|{fixture_sha256}|{gpu}|{model}|{recipe_key}|{metric}"
    return str(uuid.uuid5(NAMESPACE, key))


def _staged_rows(staging: Path) -> list[dict]:
    return [json.loads(line) for line in staging.read_text(encoding="utf-8").splitlines()]


def test_first_harvest_stages_unverified_cells(tmp_path: Path) -> None:
    staging = tmp_path / "staging.jsonl"
    result = harvest(FIXTURE, staging)

    assert result.added == 2
    assert result.skipped == 0
    fixture_sha256 = _sha256_of(FIXTURE)
    rows = _staged_rows(staging)
    assert rows == result.cells_staged

    for row in rows:
        assert row["source_class"] == "harvested"
        assert row["status"] == "unverified"
        assert row["source_url"] == SOURCE_URL
        assert row["source_sha256"] == fixture_sha256
        assert row["harvested_at"] == "2026-08-26"
        assert "note" not in row

    first, second = rows
    assert first["gpu_model_id"] == "gpu-rtx-3090"
    assert first["model_release_id"] == "model-qwen3-8b"
    assert first["recipe_id"] is None
    assert first["metric"] == "decode_tok_s"
    assert first["value"] == 42.5
    assert first["unit"] == "tok/s"
    assert first["cell_id"] == _expected_cell_id(
        fixture_sha256, "gpu-rtx-3090", "model-qwen3-8b", None, "decode_tok_s"
    )
    assert second["gpu_model_id"] == "gpu-rtx-4090"
    assert second["model_release_id"] == "model-wan22-i2v-flf2v-14b"
    assert second["recipe_id"] == "wan22-flf2v-720p-81f-v1"
    assert second["metric"] == "seconds_per_clip"
    assert second["value"] == 2957.8
    assert second["unit"] == "s"
    assert second["cell_id"] == _expected_cell_id(
        fixture_sha256,
        "gpu-rtx-4090",
        "model-wan22-i2v-flf2v-14b",
        "wan22-flf2v-720p-81f-v1",
        "seconds_per_clip",
    )


def test_rerun_is_idempotent_and_byte_identical(tmp_path: Path) -> None:
    staging = tmp_path / "staging.jsonl"
    harvest(FIXTURE, staging)
    before = staging.read_bytes()

    result = harvest(FIXTURE, staging)

    assert result.added == 0
    assert result.skipped == 2
    assert result.cells_staged == []
    assert staging.read_bytes() == before


def test_mutated_source_is_rejected_and_staging_untouched(tmp_path: Path) -> None:
    staging = tmp_path / "staging.jsonl"
    harvest(FIXTURE, staging)
    before = staging.read_text(encoding="utf-8")

    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["cells"][0]["value"] = 99.9
    mutated = tmp_path / "mutated-fixture.json"
    mutated.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SourceMutated) as excinfo:
        harvest(mutated, staging)

    error = excinfo.value
    assert error.source_url == SOURCE_URL
    assert error.staged_sha256 == _sha256_of(FIXTURE)
    assert error.incoming_sha256 == _sha256_of(mutated)
    message = str(error)
    assert error.staged_sha256 in message
    assert error.incoming_sha256 in message
    after = staging.read_text(encoding="utf-8")
    assert after == before
    assert len(after.splitlines()) == 2


def test_cell_ids_do_not_depend_on_staging(tmp_path: Path) -> None:
    staging_a = tmp_path / "a.jsonl"
    staging_b = tmp_path / "b.jsonl"

    result_a = harvest(FIXTURE, staging_a)
    result_b = harvest(FIXTURE, staging_b)

    ids_a = [cell["cell_id"] for cell in result_a.cells_staged]
    ids_b = [cell["cell_id"] for cell in result_b.cells_staged]
    assert ids_a == ids_b
    assert len(ids_a) == 2


@pytest.mark.parametrize(
    ("raw_fixture", "expected_field"),
    [
        pytest.param('{"source_url": "https://x", ', None, id="invalid-json"),
        pytest.param(
            json.dumps({"cells": []}),
            "source_url",
            id="missing-source-url",
        ),
        pytest.param(
            json.dumps(
                {
                    "source_url": "https://x",
                    "harvested_at": "2026-08-26",
                    "cells": [
                        {
                            "gpu_model_id": "gpu-rtx-3090",
                            "model_release_id": "model-qwen3-8b",
                            "metric": "decode_tok_s",
                            "unit": "tok/s",
                        }
                    ],
                }
            ),
            "value",
            id="cell-missing-required-field",
        ),
    ],
)
def test_malformed_fixture_raises_value_error(
    tmp_path: Path, raw_fixture: str, expected_field: str | None
) -> None:
    fixture = tmp_path / "broken.json"
    fixture.write_text(raw_fixture, encoding="utf-8")
    staging = tmp_path / "staging.jsonl"

    with pytest.raises(ValueError) as excinfo:
        harvest(fixture, staging)

    if expected_field is not None:
        assert expected_field in str(excinfo.value)
    assert not staging.exists()
