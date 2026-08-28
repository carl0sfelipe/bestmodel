"""Tests for the review queue (Story 4.4).

Offline by contract: planning and decision validation only — the psycopg
writer (:func:`review_queue.write_promotion_rows`) is exercised exclusively by
the real-PostgreSQL oracle, never here. Expected production ids are
recomputed in this file from the documented uuid5 recipes, independently
guarding the promotion contract.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from review_queue import build_promotion_rows, load_decisions, review_summary

NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

CELL_ID = "3d3c7e52-2b52-5f6a-9f31-4b8e1d0fa111"
VIDEO_CELL_ID = "8a4b1c90-77de-5e12-8c44-9a2b6f0d5222"
CANDIDATE_ID = "c5e21aa8-90f3-5d47-b0a6-1e7c8d3b9333"


def _cell(**overrides: object) -> dict:
    cell = {
        "cell_id": CELL_ID,
        "source_url": "https://huggingface.co/smarttasks/phi-4-GGUF/raw/main/README.md",
        "source_sha256": "a" * 64,
        "gpu_model_id": "gpu-rtx-3090",
        "model_release_id": "phi-4-Q4_K_M — GGUF (scorecard) / phi-4-Q4_K_M.gguf",
        "recipe_id": None,
        "metric": "decode_tok_s",
        "value": 82.3,
        "unit": "tok/s",
        "source_class": "harvested",
        "status": "unverified",
        "harvested_at": "2026-08-26",
    }
    cell.update(overrides)
    return cell


def _candidate(**overrides: object) -> dict:
    candidate = {
        "candidate_id": CANDIDATE_ID,
        "source_url": "https://comfyanonymous.github.io/ComfyUI_examples/wan22/wan22_i2v.json",
        "source_sha256": "b" * 64,
        "workflow_class": "KSampler",
        "models": ["wan2.2_i2v_high_noise_bf16.safetensors"],
        "width": 1280,
        "height": 720,
        "length": 81,
        "steps": 20,
        "source_class": "harvested",
        "status": "unverified_candidate",
        "harvested_at": "2026-08-26",
    }
    candidate.update(overrides)
    return candidate


def _decision(**overrides: object) -> dict:
    decision = {
        "cell_id": CELL_ID,
        "decision": "approved",
        "reviewer": "carlos",
        "decided_at": "2026-08-26",
        "binding": {"model_release_id": "model-codestral-22b"},
    }
    decision.update(overrides)
    return decision


def _decisions_file(tmp_path: Path, *records: dict) -> Path:
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    return path


# a. load_decisions validates and rejects the bad cases.
@pytest.mark.parametrize(
    ("records", "expected_error"),
    [
        ("{not json at all", "not valid JSON"),
        (
            [{"cell_id": CELL_ID, "decision": "maybe", "reviewer": "r", "decided_at": "2026-08-26"}],
            "invalid decision",
        ),
        # approved without any binding
        ([{"cell_id": CELL_ID, "decision": "approved", "reviewer": "r", "decided_at": "2026-08-26"}], "binding.model_release_id"),
        # approved with a binding that lacks model_release_id
        (
            [
                {
                    "cell_id": CELL_ID,
                    "decision": "approved",
                    "reviewer": "r",
                    "decided_at": "2026-08-26",
                    "binding": {"quantization_profile_id": "q-fp16"},
                }
            ],
            "binding.model_release_id",
        ),
        # same id decided twice with conflicting outcomes
        (
            [
                _decision(),
                {"cell_id": CELL_ID, "decision": "rejected", "reviewer": "r", "decided_at": "2026-08-26"},
            ],
            "conflicts",
        ),
        # no staged id at all
        ([{"decision": "rejected", "reviewer": "r", "decided_at": "2026-08-26"}], "cell_id/candidate_id"),
    ],
)
def test_load_decisions_rejects_bad_files(
    tmp_path: Path, records: object, expected_error: str
) -> None:
    path = tmp_path / "decisions.jsonl"
    if isinstance(records, str):
        path.write_text(records + "\n", encoding="utf-8")
    else:
        path.write_text(
            "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
        )
    with pytest.raises(ValueError, match=expected_error):
        load_decisions(path)


def test_load_decisions_accepts_and_deduplicates_identical_decisions(tmp_path: Path) -> None:
    path = _decisions_file(tmp_path, _decision(), _decision())  # exact repeat
    decisions = load_decisions(path)
    assert decisions == [_decision()]


# b. approved cell with binding -> run with harvested provenance and exact uuid5 ids.
def test_approved_cell_builds_run_with_exact_uuid5_ids_and_defaults() -> None:
    cell = _cell()
    plan = build_promotion_rows([cell], [], [_decision()])

    assert len(plan.runs) == 1
    run = plan.runs[0]
    assert run["id"] == str(uuid.uuid5(NAMESPACE, "harvested-run:" + CELL_ID))
    assert run["benchmark_scenario_id"] == str(
        uuid.uuid5(NAMESPACE, "harvested-scenario:" + CELL_ID)
    )
    assert run["hardware_submission_id"] == str(
        uuid.uuid5(NAMESPACE, "harvested-hardware:gpu-rtx-3090")
    )
    assert run["source_class"] == "harvested"
    assert run["source_url"] == cell["source_url"]
    assert run["status"] == "validated"
    assert run["client_version"] == "harvester-review-1"
    assert run["signature"] == "harvested"
    assert run["payload_digest"] == "harvested"
    assert run["model_release_id"] == "model-codestral-22b"
    assert run["recipe_id"] is None
    # documented binding defaults for a decode_tok_s cell
    assert run["quantization_profile_id"] == "q-fp16"
    assert run["inference_runtime_id"] == "llama-cpp"

    assert plan.scenarios == [
        {
            "id": str(uuid.uuid5(NAMESPACE, "harvested-scenario:" + CELL_ID)),
            "scenario_kind": "declared",
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
    ]
    assert plan.hardwares == [
        {
            "id": str(uuid.uuid5(NAMESPACE, "harvested-hardware:gpu-rtx-3090")),
            "owner_account_id": "00000000-0000-0000-0000-000000000001",
            "gpu_model_id": "gpu-rtx-3090",
            "cpu_model_id": None,
            "gpu_count": 1,
            "ram_gib": 1,
            "os_name": "harvested",
            "os_version": "unverified",
            "environment_snapshot": {"source_class": "harvested"},
        }
    ]


def test_decision_binding_overrides_the_documented_defaults() -> None:
    decision = _decision(
        binding={
            "model_release_id": "model-codestral-22b",
            "quantization_profile_id": "q-q8",
            "inference_runtime_id": "comfyui",
        }
    )
    plan = build_promotion_rows([_cell()], [], [decision])
    run = plan.runs[0]
    assert run["quantization_profile_id"] == "q-q8"
    assert run["inference_runtime_id"] == "comfyui"


# c. decode cell -> metric row; seconds_per_clip cell -> run scalar, no video metric row.
def test_decode_cell_becomes_metric_row_and_video_cell_becomes_scalar() -> None:
    plan = build_promotion_rows([_cell()], [], [_decision()])
    assert plan.metrics == [
        {
            "benchmark_run_id": str(uuid.uuid5(NAMESPACE, "harvested-run:" + CELL_ID)),
            "kind": "decode_tok_s",
            "p50_value": 82.3,
            "unit": "tok/s",
        }
    ]
    run = plan.runs[0]
    assert run["seconds_per_clip"] is None
    assert run["it_per_s"] is None
    assert run["frames_per_s"] is None

    video_decision = _decision(
        cell_id=VIDEO_CELL_ID,
        binding={
            "model_release_id": "model-codestral-22b",
            "inference_runtime_id": "comfyui",
        },
    )
    video_plan = build_promotion_rows(
        [_cell(cell_id=VIDEO_CELL_ID, metric="seconds_per_clip", value=3.2, unit="s")],
        [],
        [video_decision],
    )
    assert video_plan.metrics == []  # no metric row is fabricated for video metrics
    video_run = video_plan.runs[0]
    assert video_run["seconds_per_clip"] == 3.2
    assert video_run["it_per_s"] is None
    assert video_run["frames_per_s"] is None


# d. rejected and undecided items generate no rows; counts are honest.
def test_rejected_and_undecided_items_never_reach_production() -> None:
    cells = [
        _cell(),
        _cell(cell_id="6f6d2b11-43aa-5c88-a1b2-7c9d0e4f6bbb"),
        _cell(cell_id="1a2b3c4d-5e6f-5a7b-8c9d-0e1f2a3b4ccc"),
    ]
    decisions = [
        _decision(),
        {
            "cell_id": "6f6d2b11-43aa-5c88-a1b2-7c9d0e4f6bbb",
            "decision": "rejected",
            "reviewer": "carlos",
            "decided_at": "2026-08-26",
            "binding": {"model_release_id": "ignored-for-rejected"},
        },
    ]
    candidates = [
        _candidate(),
        _candidate(candidate_id="9d8c7b6a-5f4e-5d3c-8b2a-1f0e9d8c7ddd"),
    ]
    candidate_decisions = [
        {
            "candidate_id": "9d8c7b6a-5f4e-5d3c-8b2a-1f0e9d8c7ddd",
            "decision": "rejected",
            "reviewer": "carlos",
            "decided_at": "2026-08-26",
        }
    ]

    plan = build_promotion_rows(cells, candidates, decisions + candidate_decisions)

    assert len(plan.runs) == 1  # only the approved cell
    assert plan.runs[0]["id"] == str(uuid.uuid5(NAMESPACE, "harvested-run:" + CELL_ID))
    assert len(plan.scenarios) == 1
    assert len(plan.hardwares) == 1
    assert len(plan.metrics) == 1
    assert plan.recipes == []  # rejected candidate produced nothing
    assert plan.counts == {"approved": 1, "rejected": 2, "undecided": 2}


# e. logical idempotence: rebuilding the same promotion yields the same ids.
def test_plan_build_is_deterministic_regardless_of_decision_order() -> None:
    cells = [_cell(), _cell(cell_id=VIDEO_CELL_ID, metric="seconds_per_clip", value=3.0, unit="s")]
    candidates = [_candidate()]
    decisions = [
        _decision(),
        _decision(
            cell_id=VIDEO_CELL_ID,
            binding={"model_release_id": "model-codestral-22b", "inference_runtime_id": "comfyui"},
        ),
        _decision(candidate_id=CANDIDATE_ID, cell_id=None),
    ]

    first = build_promotion_rows(cells, candidates, decisions)
    second = build_promotion_rows(cells, candidates, list(reversed(decisions)))

    assert first == second
    assert [run["id"] for run in first.runs] == [run["id"] for run in second.runs]
    assert [recipe["recipe_id"] for recipe in first.recipes] == [
        recipe["recipe_id"] for recipe in second.recipes
    ]


# f. approved candidate -> recipe 'harv-<12>'; approved without binding -> ValueError.
def test_approved_candidate_builds_harv_recipe_and_binding_is_required() -> None:
    plan = build_promotion_rows([], [_candidate()], [_decision(candidate_id=CANDIDATE_ID, cell_id=None)])
    assert len(plan.recipes) == 1
    recipe = plan.recipes[0]
    expected_uuid = uuid.uuid5(NAMESPACE, "harvested-recipe:" + CANDIDATE_ID)
    assert recipe["recipe_id"] == "harv-" + str(expected_uuid)[:12]
    assert recipe["runtime"] == "comfyui"
    assert recipe["workflow_sha256"] is None
    assert recipe["params"] == {"width": 1280, "height": 720, "length": 81, "steps": 20}
    assert recipe["model_release_id"] == "model-codestral-22b"
    assert recipe["quantization_profile_id"] is None
    assert recipe["comfyui_version"] is None
    assert recipe["author"] == "carlos"

    with pytest.raises(ValueError, match="binding.model_release_id"):
        build_promotion_rows(
            [],
            [_candidate()],
            [
                {
                    "candidate_id": CANDIDATE_ID,
                    "decision": "approved",
                    "reviewer": "carlos",
                    "decided_at": "2026-08-26",
                }
            ],
        )


def test_review_summary_partitions_the_queue_for_humans() -> None:
    cells = [
        _cell(),
        _cell(cell_id="6f6d2b11-43aa-5c88-a1b2-7c9d0e4f6bbb"),
        _cell(cell_id="1a2b3c4d-5e6f-5a7b-8c9d-0e1f2a3b4ccc"),
    ]
    decisions = [
        _decision(),
        {
            "cell_id": "6f6d2b11-43aa-5c88-a1b2-7c9d0e4f6bbb",
            "decision": "rejected",
            "reviewer": "carlos",
            "decided_at": "2026-08-26",
        },
    ]
    candidates = [
        _candidate(),
        _candidate(candidate_id="9d8c7b6a-5f4e-5d3c-8b2a-1f0e9d8c7ddd"),
    ]
    summary = review_summary(cells, candidates, decisions)
    assert summary == {
        "cells": {"total": 3, "approved": 1, "rejected": 1, "undecided": 1},
        "candidates": {"total": 2, "approved": 0, "rejected": 0, "undecided": 2},
    }
