"""Review queue: staged harvests -> production promotion (Epic 4, Story 4.4).

Human review decisions live in a separate, commitable JSONL file; staging is
immutable and promotion never edits it. Only cells/candidates carrying an
``approved`` decision with a human binding reach production; ``rejected``
never writes anything, and ``undecided`` items stay out of production too.
Every production id is derived deterministically (uuid5) from the staged id,
so re-running the same promotion is a no-op at the database level
(``ON CONFLICT DO NOTHING``) — zero duplicates.

Production destinations (existing schema only, no new migration):

* ``benchmark_run`` with ``status='validated'``, ``source_class='harvested'``,
  the staged ``source_url`` and ``recipe_id`` when the staged cell carries one;
* ``benchmark_scenario`` with ``scenario_kind='declared'`` and every dimension
  column ``NULL`` (verified against the real 0005 CHECKs, which are
  conditional on ``'llm'``/``'video'``);
* ``hardware_submission`` community-owned row (owner
  ``00000000-0000-0000-0000-000000000001``);
* ``benchmark_metric`` rows only for token metrics (``decode_tok_s`` →
  enum value already present, unit ``tok/s``); video metrics
  (``seconds_per_clip``/``it_per_s``/``frames_per_s``) become scalar run
  columns — a metric row is never fabricated for them;
* ``recipe`` rows for approved workflow-template candidates, with a readable
  stable id ``'harv-' + first 12 chars`` of the derived uuid.

Planning (:func:`build_promotion_rows`, :func:`review_summary`) is pure
stdlib; only :func:`write_promotion_rows` touches psycopg (and is exercised
only by the real-database oracle, never by offline tests).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

#: Decision vocabulary of the review file.
VALID_DECISIONS = ("approved", "rejected")

#: Documented binding defaults (overridable by the decision itself).
DEFAULT_QUANTIZATION_PROFILE_ID = "q-fp16"
DEFAULT_INFERENCE_RUNTIME_ID = "llama-cpp"  # for decode_tok_s cells

COMMUNITY_OWNER_ID = "00000000-0000-0000-0000-000000000001"
CLIENT_VERSION = "harvester-review-1"
HARVESTED_SIGNATURE = "harvested"
HARVESTED_PAYLOAD_DIGEST = "harvested"
SOURCE_CLASS = "harvested"
STATUS_VALIDATED = "validated"

#: Cell metrics that map to scalar benchmark_run columns instead of a
#: benchmark_metric row (video measurements; AD-1: never reuse token fields).
SCALAR_RUN_METRICS = ("seconds_per_clip", "it_per_s", "frames_per_s")

_DECIDED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Decision file (the review "commit")
# ---------------------------------------------------------------------------


def _decision_subject(record: dict[str, Any], line_number: int) -> str:
    cell_id = record.get("cell_id")
    candidate_id = record.get("candidate_id")
    if cell_id is not None and candidate_id is not None:
        raise ValueError(
            f"decision line {line_number} declares both cell_id and candidate_id; "
            "one decision covers exactly one staged id"
        )
    for name, value in (("cell_id", cell_id), ("candidate_id", candidate_id)):
        if value is not None:
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"decision line {line_number} has field '{name}' that is not a non-empty string"
                )
            return value
    raise ValueError(f"decision line {line_number} is missing cell_id/candidate_id")


def _validated_decision(record: dict[str, Any], line_number: int) -> tuple[str, str, dict[str, Any]]:
    """Validates one decision record; returns (subject_id, decision, record)."""
    if not isinstance(record, dict):
        raise ValueError(f"decision line {line_number} is not a JSON object")
    subject_id = _decision_subject(record, line_number)
    decision = record.get("decision")
    if decision not in VALID_DECISIONS:
        raise ValueError(
            f"decision line {line_number} has invalid decision {decision!r}: "
            f"expected one of {VALID_DECISIONS}"
        )
    reviewer = record.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer:
        raise ValueError(f"decision line {line_number} has missing or empty field 'reviewer'")
    decided_at = record.get("decided_at")
    if not isinstance(decided_at, str) or not _DECIDED_AT_RE.match(decided_at):
        raise ValueError(
            f"decision line {line_number} has field 'decided_at' not in YYYY-MM-DD format"
        )
    if decision == "approved":
        binding = record.get("binding")
        model_release_id = binding.get("model_release_id") if isinstance(binding, dict) else None
        if not isinstance(model_release_id, str) or not model_release_id:
            raise ValueError(
                f"decision line {line_number} is 'approved' without binding.model_release_id"
            )
    # A rejected decision's binding field is ignored entirely.
    return subject_id, decision, record


def load_decisions(path: Path) -> list[dict[str, Any]]:
    """Loads and validates the decision JSONL file.

    Raises ``ValueError`` naming the problem: a line that is not valid JSON,
    an invalid ``decision`` value, an ``approved`` decision without
    ``binding.model_release_id``, or two decisions for the same id with
    conflicting outcomes. An exact repeated decision for the same id is
    deduplicated (the first occurrence wins).
    """
    decisions: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"decision line {line_number} is not valid JSON: {error}") from error
        subject_id, decision, record = _validated_decision(record, line_number)
        previous = seen.get(subject_id)
        if previous is not None:
            if previous != decision:
                raise ValueError(
                    f"decision line {line_number} conflicts with an earlier decision "
                    f"for id {subject_id!r}: {previous!r} vs {decision!r}"
                )
            continue  # identical repeat: keep the first, do not double count
        seen[subject_id] = decision
        decisions.append(record)
    return decisions


def _decision_by_id(decisions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """First decision wins per staged id (callers may pass un-validated lists)."""
    by_id: dict[str, dict[str, Any]] = {}
    for record in decisions:
        subject_id, _, _ = _validated_decision(record, 0)
        by_id.setdefault(subject_id, record)
    return by_id


def _decision_outcome(record: dict[str, Any] | None) -> str:
    return record["decision"] if record is not None else "undecided"


# ---------------------------------------------------------------------------
# Promotion plan (pure, stdlib only)
# ---------------------------------------------------------------------------


@dataclass
class PromotionPlan:
    """Everything ready to be written to production, plus honest counts."""

    runs: list[dict[str, Any]] = field(default_factory=list)
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    hardwares: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    recipes: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(
        default_factory=lambda: {"approved": 0, "rejected": 0, "undecided": 0}
    )


def _approved_binding(decision_record: dict[str, Any], staged_id: str) -> dict[str, Any]:
    binding = decision_record.get("binding")
    model_release_id = binding.get("model_release_id") if isinstance(binding, dict) else None
    if not isinstance(model_release_id, str) or not model_release_id:
        raise ValueError(
            f"approved staged item {staged_id!r} has no binding.model_release_id; "
            "a cell only reaches production with a human binding"
        )
    return binding


def _scenario_row(scenario_id: str) -> dict[str, Any]:
    return {
        "id": scenario_id,
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


def _hardware_row(hardware_id: str, gpu_model_id: str) -> dict[str, Any]:
    return {
        "id": hardware_id,
        "owner_account_id": COMMUNITY_OWNER_ID,
        "gpu_model_id": gpu_model_id,
        "cpu_model_id": None,  # column exists in hardware_submission; harvests have no cpu claim
        "gpu_count": 1,
        "ram_gib": 1,
        "os_name": "harvested",
        "os_version": "unverified",
        "environment_snapshot": {"source_class": "harvested"},
    }


def _plan_cell_run(
    cell: dict[str, Any],
    binding: dict[str, Any],
    runs: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    hardwares: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    planned_hardware_ids: set[str],
) -> None:
    cell_id = cell["cell_id"]
    metric = cell["metric"]
    if metric not in SCALAR_RUN_METRICS and metric != "decode_tok_s":
        raise ValueError(
            f"staged cell {cell_id!r} has metric {metric!r} with no documented production destination"
        )

    run_id = str(uuid.uuid5(UUID_NAMESPACE, "harvested-run:" + cell_id))
    scenario_id = str(uuid.uuid5(UUID_NAMESPACE, "harvested-scenario:" + cell_id))
    hardware_id = str(uuid.uuid5(UUID_NAMESPACE, "harvested-hardware:" + cell["gpu_model_id"]))

    scalars: dict[str, Any] = {name: None for name in SCALAR_RUN_METRICS}
    if metric == "decode_tok_s":
        inference_runtime_id = binding.get("inference_runtime_id") or DEFAULT_INFERENCE_RUNTIME_ID
        metrics.append(
            {
                "benchmark_run_id": run_id,
                "kind": metric,
                "p50_value": float(cell["value"]),
                "unit": cell["unit"],
            }
        )
    else:
        inference_runtime_id = binding.get("inference_runtime_id")
        if not inference_runtime_id:
            raise ValueError(
                f"approved cell {cell_id!r} with metric {metric!r} needs "
                "binding.inference_runtime_id (no default is documented for video metrics)"
            )
        scalars[metric] = cell["value"]

    if hardware_id not in planned_hardware_ids:
        planned_hardware_ids.add(hardware_id)
        hardwares.append(_hardware_row(hardware_id, cell["gpu_model_id"]))
    scenarios.append(_scenario_row(scenario_id))
    runs.append(
        {
            "id": run_id,
            "hardware_submission_id": hardware_id,
            "model_release_id": binding["model_release_id"],
            "quantization_profile_id": binding.get("quantization_profile_id")
            or DEFAULT_QUANTIZATION_PROFILE_ID,
            "inference_runtime_id": inference_runtime_id,
            "benchmark_scenario_id": scenario_id,
            "status": STATUS_VALIDATED,
            "client_version": CLIENT_VERSION,
            "signature": HARVESTED_SIGNATURE,
            "payload_digest": HARVESTED_PAYLOAD_DIGEST,
            "recipe_id": cell.get("recipe_id"),
            "source_class": SOURCE_CLASS,
            "seconds_per_clip": scalars["seconds_per_clip"],
            "it_per_s": scalars["it_per_s"],
            "frames_per_s": scalars["frames_per_s"],
            "source_url": cell["source_url"],
        }
    )


def _plan_candidate_recipe(
    candidate: dict[str, Any],
    decision_record: dict[str, Any],
    recipes: list[dict[str, Any]],
) -> None:
    candidate_id = candidate["candidate_id"]
    binding = _approved_binding(decision_record, candidate_id)
    recipe_uuid = uuid.uuid5(UUID_NAMESPACE, "harvested-recipe:" + candidate_id)
    recipes.append(
        {
            "recipe_id": "harv-" + str(recipe_uuid)[:12],
            "runtime": "comfyui",
            "workflow_sha256": None,
            "params": {
                "width": candidate["width"],
                "height": candidate["height"],
                "length": candidate["length"],
                "steps": candidate["steps"],
            },
            "model_release_id": binding["model_release_id"],
            "quantization_profile_id": None,
            "comfyui_version": None,
            "author": decision_record["reviewer"],
        }
    )


def build_promotion_rows(
    cells_staging: list[dict[str, Any]],
    candidates_staging: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> PromotionPlan:
    """Partitions staging by decision and builds the production rows.

    Only ``approved`` items generate rows; ``rejected`` and ``undecided``
    never reach production. The plan carries the honest partition counts
    (``counts``) over cells and candidates together.
    """
    plan = PromotionPlan()
    decision_by_id = _decision_by_id(decisions)
    planned_hardware_ids: set[str] = set()

    for cell in cells_staging:
        record = decision_by_id.get(cell["cell_id"])
        plan.counts[_decision_outcome(record)] += 1
        if record is None or record["decision"] != "approved":
            continue  # rejected and undecided cells never reach production
        _plan_cell_run(
            cell,
            _approved_binding(record, cell["cell_id"]),
            plan.runs,
            plan.scenarios,
            plan.hardwares,
            plan.metrics,
            planned_hardware_ids,
        )

    for candidate in candidates_staging:
        record = decision_by_id.get(candidate["candidate_id"])
        plan.counts[_decision_outcome(record)] += 1
        if record is None or record["decision"] != "approved":
            continue  # rejected and undecided candidates never reach production
        _plan_candidate_recipe(candidate, record, plan.recipes)

    return plan


def review_summary(
    cells_staging: list[dict[str, Any]],
    candidates_staging: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Human-readable queue counts: totals partitioned by decision outcome."""
    decision_by_id = _decision_by_id(decisions)

    def _partition(items: list[dict[str, Any]], id_field: str) -> dict[str, int]:
        counts = {"total": len(items), "approved": 0, "rejected": 0, "undecided": 0}
        for item in items:
            record = decision_by_id.get(item[id_field])
            counts[_decision_outcome(record)] += 1
        return counts

    return {
        "cells": _partition(cells_staging, "cell_id"),
        "candidates": _partition(candidates_staging, "candidate_id"),
    }


# ---------------------------------------------------------------------------
# Writer (the only psycopg-touching part; exercised by the real-PG oracle)
# ---------------------------------------------------------------------------


@dataclass
class WriteReport:
    runs_written: int
    recipes_written: int


_INSERT_SCENARIO = (
    "INSERT INTO benchmark_scenario "
    "(id, scenario_kind, prompt_tokens, generated_tokens, context_tokens, "
    "batch_size, tensor_parallel, width, height, frames, steps, cfg, shift, seed) "
    "VALUES (%(id)s, %(scenario_kind)s, %(prompt_tokens)s, %(generated_tokens)s, "
    "%(context_tokens)s, %(batch_size)s, %(tensor_parallel)s, %(width)s, %(height)s, "
    "%(frames)s, %(steps)s, %(cfg)s, %(shift)s, %(seed)s) "
    "ON CONFLICT (id) DO NOTHING"
)

_INSERT_HARDWARE = (
    "INSERT INTO hardware_submission "
    "(id, owner_account_id, gpu_model_id, cpu_model_id, gpu_count, ram_gib, "
    "os_name, os_version, environment_snapshot) "
    "VALUES (%(id)s, %(owner_account_id)s, %(gpu_model_id)s, %(cpu_model_id)s, "
    "%(gpu_count)s, %(ram_gib)s, %(os_name)s, %(os_version)s, %(environment_snapshot)s) "
    "ON CONFLICT (id) DO NOTHING"
)

_INSERT_RECIPE = (
    "INSERT INTO recipe "
    "(recipe_id, runtime, workflow_sha256, params, model_release_id, "
    "quantization_profile_id, comfyui_version, author) "
    "VALUES (%(recipe_id)s, %(runtime)s, %(workflow_sha256)s, %(params)s, "
    "%(model_release_id)s, %(quantization_profile_id)s, %(comfyui_version)s, %(author)s) "
    "ON CONFLICT (recipe_id) DO NOTHING RETURNING recipe_id"
)

_INSERT_RUN = (
    "INSERT INTO benchmark_run "
    "(id, hardware_submission_id, model_release_id, quantization_profile_id, "
    "inference_runtime_id, benchmark_scenario_id, status, client_version, "
    "signature, payload_digest, recipe_id, source_class, seconds_per_clip, "
    "it_per_s, frames_per_s, source_url) "
    "VALUES (%(id)s, %(hardware_submission_id)s, %(model_release_id)s, "
    "%(quantization_profile_id)s, %(inference_runtime_id)s, %(benchmark_scenario_id)s, "
    "%(status)s, %(client_version)s, %(signature)s, %(payload_digest)s, "
    "%(recipe_id)s, %(source_class)s, %(seconds_per_clip)s, %(it_per_s)s, "
    "%(frames_per_s)s, %(source_url)s) "
    "ON CONFLICT (id) DO NOTHING RETURNING id"
)

_INSERT_METRIC = (
    "INSERT INTO benchmark_metric (benchmark_run_id, kind, p50_value, unit) "
    "VALUES (%(benchmark_run_id)s, %(kind)s, %(p50_value)s, %(unit)s)"
)


def write_promotion_rows(connection: Any, plan: PromotionPlan) -> WriteReport:
    """Writes the plan to production through real psycopg.

    Scenarios/hardware/recipes are ``ON CONFLICT DO NOTHING``; runs use
    ``ON CONFLICT (id) DO NOTHING RETURNING id`` so metrics are written only
    for runs actually inserted in *this* execution — re-running the same plan
    reports ``runs_written == 0`` and duplicates nothing. Commits on success.
    """
    from psycopg.types.json import Json  # psycopg is only required by the writer

    with connection.cursor() as cursor:
        for scenario in plan.scenarios:
            cursor.execute(_INSERT_SCENARIO, scenario)
        for hardware in plan.hardwares:
            bound = dict(hardware)
            bound["environment_snapshot"] = Json(bound["environment_snapshot"])
            cursor.execute(_INSERT_HARDWARE, bound)
        recipes_written = 0
        for recipe in plan.recipes:
            bound = dict(recipe)
            bound["params"] = Json(bound["params"])
            cursor.execute(_INSERT_RECIPE, bound)
            recipes_written += len(cursor.fetchall())
        written_run_ids: set[str] = set()
        for run in plan.runs:
            cursor.execute(_INSERT_RUN, run)
            written_run_ids.update(str(row[0]) for row in cursor.fetchall())
        for metric in plan.metrics:
            if str(metric["benchmark_run_id"]) in written_run_ids:
                cursor.execute(_INSERT_METRIC, metric)

    connection.commit()
    return WriteReport(runs_written=len(written_run_ids), recipes_written=recipes_written)
