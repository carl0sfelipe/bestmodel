"""Tests for the ComfyUI workflow-template harvester (Story 4.3).

Expected candidate ids are recomputed here from the documented uuid5 recipe, so
this file independently guards the staging contract (candidates are never
published recipes, unverified_candidate, byte-stable reruns, SourceMutated on
changed sources) against accidental drift. The real template fixture is
committed verbatim; no test touches the network.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from comfy_template_harvester import extract_recipe_candidates, stage_recipe_candidates
from harvester import SourceMutated

FIXTURES = Path(__file__).parent / "fixtures"
TEMPLATE = FIXTURES / "comfy-template.json"
META = FIXTURES / "comfy-template.meta.json"
NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

SYNTHETIC_SOURCE_URL = "https://example.invalid/comfyui/wan-t2v-synthetic"


def _meta() -> dict[str, str]:
    return json.loads(META.read_text(encoding="utf-8"))


def _real_fixture() -> dict[str, Any]:
    meta = _meta()
    return extract_recipe_candidates(
        TEMPLATE.read_text(encoding="utf-8"), meta["source_url"], meta["fetched_at"]
    )


def _sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _expected_candidate_id(
    fixture_sha256: str,
    workflow_class: str,
    params: dict[str, int | None],
    models: list[str],
) -> str:
    tokens = {key: "null" if value is None else str(value) for key, value in params.items()}
    key = (
        f"{_meta()['source_url']}|{fixture_sha256}|{workflow_class}"
        f"|{tokens['width']}x{tokens['height']}x{tokens['length']}x{tokens['steps']}"
        f"|{','.join(sorted(models))}"
    )
    return str(uuid.uuid5(NAMESPACE, key))


def _staged_rows(staging: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in staging.read_text(encoding="utf-8").splitlines()]


def test_real_template_yields_wan_candidates_with_models() -> None:
    meta = _meta()
    fixture = _real_fixture()

    assert fixture["source_url"] == meta["source_url"]
    assert fixture["harvested_at"] == meta["fetched_at"]
    assert fixture["source_sha256"] == _sha256_of_text(TEMPLATE.read_text(encoding="utf-8"))
    assert len(fixture["candidates"]) >= 1

    matching = [
        candidate
        for candidate in fixture["candidates"]
        if any(token in candidate["workflow_class"] for token in ("Wan", "Video", "Sampler"))
        and candidate["models"]
    ]
    assert matching, f"no Wan/Video/Sampler candidate with models: {fixture['candidates']}"

    # Exact values read verbatim from the committed UI-format template: the
    # WanImageToVideo latent declares 512x512 for 33 frames; the KSampler runs
    # 20 steps; the three spec-listed loaders carry the Wan 2.1 model files.
    by_class = {candidate["workflow_class"]: candidate for candidate in fixture["candidates"]}
    wan = by_class["WanImageToVideo"]
    assert (wan["width"], wan["height"], wan["length"], wan["steps"]) == (512, 512, 33, None)
    sampler = by_class["KSampler"]
    assert (sampler["width"], sampler["height"], sampler["length"], sampler["steps"]) == (
        None,
        None,
        None,
        20,
    )
    expected_models = [
        "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "wan2.1_i2v_480p_14B_fp16.safetensors",
        "wan_2.1_vae.safetensors",
    ]
    assert wan["models"] == expected_models
    assert sampler["models"] == expected_models


def test_extraction_and_candidate_ids_are_deterministic(tmp_path: Path) -> None:
    first = _real_fixture()
    second = _real_fixture()
    assert first == second

    staging_a = tmp_path / "a.jsonl"
    staging_b = tmp_path / "b.jsonl"
    result_a = stage_recipe_candidates(first, staging_a)
    result_b = stage_recipe_candidates(second, staging_b)

    ids_a = [row["candidate_id"] for row in result_a.candidates_staged]
    ids_b = [row["candidate_id"] for row in result_b.candidates_staged]
    assert ids_a == ids_b
    assert len(ids_a) == len(first["candidates"])
    assert staging_a.read_bytes() == staging_b.read_bytes()


def test_stage_twice_is_idempotent_and_byte_identical(tmp_path: Path) -> None:
    fixture = _real_fixture()
    staging = tmp_path / "recipes.jsonl"

    first = stage_recipe_candidates(fixture, staging)
    after_first = staging.read_bytes()

    second = stage_recipe_candidates(fixture, staging)

    assert first.added == len(fixture["candidates"])
    assert first.skipped == 0
    assert second.added == 0
    assert second.skipped == first.added
    assert second.candidates_staged == []
    assert staging.read_bytes() == after_first

    fixture_sha256 = fixture["source_sha256"]
    rows = _staged_rows(staging)
    assert rows == first.candidates_staged
    for row in rows:
        assert row["source_class"] == "harvested"
        assert row["status"] == "unverified_candidate"
        assert row["source_url"] == fixture["source_url"]
        assert row["source_sha256"] == fixture_sha256
        assert row["harvested_at"] == fixture["harvested_at"]
        assert row["candidate_id"] == _expected_candidate_id(
            fixture_sha256, row["workflow_class"], row, row["models"]
        )


def test_mutated_template_raises_source_mutated_and_staging_untouched(tmp_path: Path) -> None:
    meta = _meta()
    staging = tmp_path / "recipes.jsonl"
    stage_recipe_candidates(_real_fixture(), staging)
    before = staging.read_bytes()

    # Same source_url, edited text (reserialized): a different content hash.
    mutated_text = json.dumps(json.loads(TEMPLATE.read_text(encoding="utf-8")))
    mutated_fixture = extract_recipe_candidates(mutated_text, meta["source_url"], meta["fetched_at"])

    with pytest.raises(SourceMutated) as excinfo:
        stage_recipe_candidates(mutated_fixture, staging)

    error = excinfo.value
    assert error.source_url == meta["source_url"]
    assert error.staged_sha256 == _sha256_of_text(TEMPLATE.read_text(encoding="utf-8"))
    assert error.incoming_sha256 == _sha256_of_text(mutated_text)
    message = str(error)
    assert error.staged_sha256 in message
    assert error.incoming_sha256 in message
    assert staging.read_bytes() == before
    assert len(staging.read_text(encoding="utf-8").splitlines()) == 2


def test_synthetic_api_format_params_exact_and_unknown_format_rejected() -> None:
    template = json.dumps(
        {
            "6": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "wan2.1_t2v_14B_fp16.safetensors",
                    "weight_dtype": "default",
                },
            },
            "7": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                    "type": "wan",
                    "device": "default",
                },
            },
            "8": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "wan_2.1_vae.safetensors"},
            },
            "10": {
                "class_type": "WanImageToVideo",
                "inputs": {
                    "positive": ["7", 0],
                    "negative": ["7", 0],
                    "vae": ["8", 0],
                    "width": 832,
                    "height": 480,
                    "length": 49,
                    "batch_size": 1,
                },
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["6", 0],
                    "positive": ["10", 0],
                    "negative": ["10", 1],
                    "latent_image": ["10", 2],
                    "seed": 42,
                    "steps": 20,
                    "cfg": 6.0,
                    "sampler_name": "uni_pc",
                    "scheduler": "simple",
                    "denoise": 1.0,
                },
            },
        }
    )
    fixture = extract_recipe_candidates(template, SYNTHETIC_SOURCE_URL, "2026-08-26")

    expected_models = [
        "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "wan2.1_t2v_14B_fp16.safetensors",
        "wan_2.1_vae.safetensors",
    ]
    assert fixture["source_url"] == SYNTHETIC_SOURCE_URL
    assert fixture["source_sha256"] == _sha256_of_text(template)
    assert fixture["candidates"] == [
        {
            "workflow_class": "WanImageToVideo",
            "models": expected_models,
            "width": 832,
            "height": 480,
            "length": 49,
            "steps": None,
        },
        {
            "workflow_class": "KSampler",
            "models": expected_models,
            "width": None,
            "height": None,
            "length": None,
            "steps": 20,
        },
    ]

    with pytest.raises(ValueError, match="unknown workflow template format"):
        extract_recipe_candidates(
            json.dumps({"nodes": {"7": "not-a-list"}}), SYNTHETIC_SOURCE_URL, "2026-08-26"
        )
    with pytest.raises(ValueError, match="unknown workflow template format"):
        extract_recipe_candidates(json.dumps([1, 2]), SYNTHETIC_SOURCE_URL, "2026-08-26")
    with pytest.raises(ValueError, match="not valid JSON"):
        extract_recipe_candidates("{not json", SYNTHETIC_SOURCE_URL, "2026-08-26")


@pytest.mark.parametrize(
    ("raw_fixture", "expected_field"),
    [
        pytest.param(
            json.dumps({"source_url": "https://x", "candidates": []}),
            "source_sha256",
            id="missing-source-sha",
        ),
        pytest.param(
            json.dumps(
                {
                    "source_url": "https://x",
                    "source_sha256": "0" * 64,
                    "harvested_at": "2026-08-26",
                    "candidates": {},
                }
            ),
            "candidates",
            id="candidates-not-a-list",
        ),
        pytest.param(
            json.dumps(
                {
                    "source_url": "https://x",
                    "source_sha256": "0" * 64,
                    "harvested_at": "2026-08-26",
                    "candidates": [{"workflow_class": "KSampler", "models": ["m.safetensors"]}],
                }
            ),
            "width",
            id="candidate-missing-required-field",
        ),
        pytest.param(
            json.dumps(
                {
                    "source_url": "https://x",
                    "source_sha256": "0" * 64,
                    "harvested_at": "2026-08-26",
                    "candidates": [
                        {
                            "workflow_class": "KSampler",
                            "models": ["m.safetensors"],
                            "width": "512",
                            "height": None,
                            "length": None,
                            "steps": 20,
                        }
                    ],
                }
            ),
            "width",
            id="candidate-param-not-a-positive-int",
        ),
    ],
)
def test_malformed_staging_fixture_raises_and_writes_nothing(
    tmp_path: Path, raw_fixture: str, expected_field: str
) -> None:
    staging = tmp_path / "staging.jsonl"

    with pytest.raises(ValueError) as excinfo:
        stage_recipe_candidates(json.loads(raw_fixture), staging)

    assert expected_field in str(excinfo.value)
    assert not staging.exists()
