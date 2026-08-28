"""ComfyUI workflow-template harvester (Epic 4, Story 4.3).

Extracts recipe candidates from ComfyUI workflow templates (the versioned
template library, e.g. the Wan video workflows): every sampler node yields one
candidate with the workflow-wide model files and the width/height/length/steps
parameters readable from that sampler's own inputs. Two template shapes are
accepted — the exported UI format (``{"nodes": [...]}`` with positional
``widgets_values``) and the API format (``{"<id>": {"class_type", "inputs"}}``
with named inputs); anything else is rejected with ``ValueError``.

Extraction is conservative and deterministic: nothing is inferred. A parameter
that cannot be read deterministically from the template text stays ``null``
(partial params), and an unreadable value never fails the harvest. Candidates
are never published recipes: ``stage_recipe_candidates`` appends them to a
JSONL staging file with ``source_class="harvested"`` and
``status="unverified_candidate"`` (promotion is the review queue of Story 4.4).
Staging is idempotent per ``candidate_id`` (uuid5 over the documented identity
recipe) and a source whose content hash changed under the same ``source_url``
is rejected with ``SourceMutated`` (imported from the 4.1 framework) before
anything is written.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from harvester import SourceMutated, UUID_NAMESPACE

#: Loader node classes whose inputs carry model file names (spec 4.3).
MODEL_NODE_TYPES = ("UNETLoader", "CLIPLoader", "VAELoader", "CheckpointLoaderSimple")

#: File extensions that mark a string input as a model file name.
MODEL_FILE_EXTENSIONS = (".safetensors", ".gguf", ".sft", ".ckpt", ".pt", ".pth", ".bin")

#: Parameters of interest read from the sampler node's own inputs.
SAMPLER_PARAM_FIELDS = ("width", "height", "length", "steps")

#: Widget-input layouts used to decode positional ``widgets_values`` of UI-format
#: sampler nodes. ComfyUI serializes widget values in the order the inputs are
#: declared on the node type, so a layout only applies when its length matches
#: the serialized array exactly; any other sampler class (or a length mismatch)
#: keeps conservative ``null`` parameters.
UI_WIDGET_LAYOUTS: dict[str, tuple[tuple[str, ...], ...]] = {
    # Modern exports insert the seed's control_after_generate combo after seed;
    # legacy exports serialize the six original widgets only.
    "KSampler": (
        (
            "seed",
            "control_after_generate",
            "steps",
            "cfg",
            "sampler_name",
            "scheduler",
            "denoise",
        ),
        ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"),
    ),
    "KSamplerAdvanced": (
        (
            "add_noise",
            "noise_seed",
            "control_after_generate",
            "steps",
            "cfg",
            "sampler_name",
            "scheduler",
            "start_at_step",
            "end_at_step",
            "return_with_leftover_noise",
        ),
    ),
}

#: The Wan video latent nodes (class starts with "Wan" and ends with
#: "ToVideo") all declare (width, height, length, batch_size) as widgets.
WAN_TO_VIDEO_WIDGETS: tuple[str, ...] = ("width", "height", "length", "batch_size")

REQUIRED_CANDIDATE_FIELDS = ("workflow_class", "models") + SAMPLER_PARAM_FIELDS


@dataclass
class StageResult:
    """Outcome of staging recipe candidates (HarvestResult-like)."""

    added: int
    skipped: int
    candidates_staged: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Format detection and node access
# ---------------------------------------------------------------------------


def _detect_format(payload: dict[str, Any]) -> str:
    """Classifies a parsed template as ``"ui"`` or ``"api"``; ``ValueError`` otherwise."""
    if isinstance(payload.get("nodes"), list):
        return "ui"
    if payload and all(
        isinstance(node, dict) and isinstance(node.get("class_type"), str)
        for node in payload.values()
    ):
        return "api"
    raise ValueError(
        "unknown workflow template format: expected UI format "
        '({"nodes": [...]}) or API format ({"<id>": {"class_type", "inputs"}})'
    )


def _iter_nodes(payload: dict[str, Any], workflow_format: str) -> Iterator[dict[str, Any]]:
    """Yields the well-formed node objects of the template, in serialized order."""
    if workflow_format == "ui":
        for node in payload["nodes"]:
            if isinstance(node, dict) and isinstance(node.get("type"), str):
                yield node
    else:
        for node in payload.values():
            yield node


def _node_class(node: dict[str, Any], workflow_format: str) -> str:
    return node["type"] if workflow_format == "ui" else node["class_type"]


def _is_sampler(class_type: str) -> bool:
    """Same rule as the benchmark probe (Story 1.2): KSampler family + Wan ToVideo family."""
    return "Sampler" in class_type or class_type.endswith("ToVideo")


# ---------------------------------------------------------------------------
# Model files and sampler parameters
# ---------------------------------------------------------------------------


def _is_model_file_name(value: Any) -> bool:
    return isinstance(value, str) and value.lower().endswith(MODEL_FILE_EXTENSIONS)


def _node_model_files(node: dict[str, Any], workflow_format: str) -> Iterator[str]:
    """Yields the model file names found in a loader node's widget/input values."""
    if workflow_format == "ui":
        widgets = node.get("widgets_values")
        if isinstance(widgets, list):
            for value in widgets:
                if _is_model_file_name(value):
                    yield value
    else:
        inputs = node.get("inputs")
        if isinstance(inputs, dict):
            for value in inputs.values():
                if _is_model_file_name(value):
                    yield value


def _positive_int(value: Any) -> int | None:
    """Accepts strict positive ints only (bools/floats/strings/links stay null)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None


def _api_sampler_params(node: dict[str, Any]) -> dict[str, int | None]:
    """Reads named inputs from an API-format sampler node."""
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    return {field: _positive_int(inputs.get(field)) for field in SAMPLER_PARAM_FIELDS}


def _ui_widget_names(node: dict[str, Any], class_type: str) -> list[str] | None:
    """Resolves the widget-input names that align, in order, with ``widgets_values``.

    Preferred source: the node's own ``inputs`` list, when it declares widget
    entries (entries without a ``link``) whose count matches ``widgets_values``.
    Fallback: the documented layouts of the core sampler classes above. Returns
    ``None`` when no deterministic alignment exists (parameters stay null).
    """
    widgets = node.get("widgets_values")
    if not isinstance(widgets, list):
        return None
    inputs = node.get("inputs")
    if isinstance(inputs, list):
        widget_entries = [
            entry.get("name")
            for entry in inputs
            if isinstance(entry, dict) and "link" not in entry and isinstance(entry.get("name"), str)
        ]
        if widget_entries:
            return widget_entries if len(widget_entries) == len(widgets) else None
    layouts = UI_WIDGET_LAYOUTS.get(class_type)
    if layouts is None and class_type.startswith("Wan") and class_type.endswith("ToVideo"):
        layouts = (WAN_TO_VIDEO_WIDGETS,)
    if layouts is None:
        return None
    for layout in layouts:
        if len(layout) == len(widgets):
            return list(layout)
    return None


def _ui_sampler_params(node: dict[str, Any], class_type: str) -> dict[str, int | None]:
    """Reads positional widget values from a UI-format sampler node."""
    widgets = node.get("widgets_values")
    names = _ui_widget_names(node, class_type)
    params: dict[str, int | None] = {field: None for field in SAMPLER_PARAM_FIELDS}
    if names is None:
        return params
    for index, name in enumerate(names):
        if name in params:
            params[name] = _positive_int(widgets[index])
    return params


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_recipe_candidates(
    template_text: str, source_url: str, harvested_at: str
) -> dict[str, Any]:
    """Extracts recipe candidates from one ComfyUI workflow template.

    Returns the fixture dict consumed by :func:`stage_recipe_candidates`:
    ``{"source_url", "harvested_at", "source_sha256", "candidates": [...]}``
    where each candidate is ``{"workflow_class", "models", "width", "height",
    "length", "steps"}`` (unreadable parameters are ``null``).
    """
    try:
        payload = json.loads(template_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"template is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(
            "unknown workflow template format: root is not a JSON object "
            '(expected {"nodes": [...]} or {"<id>": {"class_type", "inputs"}})'
        )
    workflow_format = _detect_format(payload)
    nodes = list(_iter_nodes(payload, workflow_format))

    models = sorted(
        {
            model_file
            for node in nodes
            if _node_class(node, workflow_format) in MODEL_NODE_TYPES
            for model_file in _node_model_files(node, workflow_format)
        }
    )

    candidates: list[dict[str, Any]] = []
    for node in nodes:
        class_type = _node_class(node, workflow_format)
        if not _is_sampler(class_type):
            continue
        if workflow_format == "ui":
            params = _ui_sampler_params(node, class_type)
        else:
            params = _api_sampler_params(node)
        candidates.append(
            {
                "workflow_class": class_type,
                "models": models,
                **params,
            }
        )

    return {
        "source_url": source_url,
        "harvested_at": harvested_at,
        "source_sha256": hashlib.sha256(template_text.encode("utf-8")).hexdigest(),
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


def _param_token(value: int | None) -> str:
    return "null" if value is None else str(value)


def _derive_candidate_id(
    source_url: str,
    source_sha256: str,
    workflow_class: str,
    params: dict[str, int | None],
    models: list[str],
) -> str:
    """uuid5 over the documented identity: source, sha, class, params, models."""
    key = (
        f"{source_url}|{source_sha256}|{workflow_class}"
        f"|{_param_token(params['width'])}x{_param_token(params['height'])}"
        f"x{_param_token(params['length'])}x{_param_token(params['steps'])}"
        f"|{','.join(sorted(models))}"
    )
    return str(uuid.uuid5(UUID_NAMESPACE, key))


def _validate_fixture(fixture: Any) -> tuple[str, str, str, list[dict[str, Any]]]:
    """Validates the whole fixture before anything is written; raises ``ValueError``."""
    if not isinstance(fixture, dict):
        raise ValueError("fixture is not an object")
    if not isinstance(fixture.get("source_url"), str):
        raise ValueError("fixture field 'source_url' is missing or not a string")
    source_sha256 = fixture.get("source_sha256")
    if not (
        isinstance(source_sha256, str)
        and len(source_sha256) == 64
        and all(char in "0123456789abcdef" for char in source_sha256)
    ):
        raise ValueError("fixture field 'source_sha256' is missing or not a sha256 hex digest")
    harvested_at = fixture.get("harvested_at")
    if not isinstance(harvested_at, str):
        raise ValueError("fixture field 'harvested_at' is missing or not a string")
    if not isinstance(fixture.get("candidates"), list):
        raise ValueError("fixture field 'candidates' is missing or not a list")
    for index, candidate in enumerate(fixture["candidates"]):
        if not isinstance(candidate, dict):
            raise ValueError(f"fixture field 'candidates[{index}]' is not an object")
        for field in REQUIRED_CANDIDATE_FIELDS:
            if field not in candidate:
                raise ValueError(f"fixture field 'candidates[{index}].{field}' is missing")
        if not isinstance(candidate["workflow_class"], str) or not candidate["workflow_class"]:
            raise ValueError(
                f"fixture field 'candidates[{index}].workflow_class' is not a non-empty string"
            )
        if not isinstance(candidate["models"], list) or not all(
            isinstance(model, str) for model in candidate["models"]
        ):
            raise ValueError(
                f"fixture field 'candidates[{index}].models' is not a list of strings"
            )
        for field in SAMPLER_PARAM_FIELDS:
            value = candidate[field]
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(
                    f"fixture field 'candidates[{index}].{field}' is not a positive int or null"
                )
    return fixture["source_url"], source_sha256, harvested_at, fixture["candidates"]


def _load_staging(staging_path: Path) -> list[dict[str, Any]]:
    if not staging_path.exists():
        return []
    rows = []
    for line in staging_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _staged_row(
    candidate: dict[str, Any], source_url: str, source_sha256: str, harvested_at: str
) -> dict[str, Any]:
    params = {field: candidate[field] for field in SAMPLER_PARAM_FIELDS}
    return {
        "candidate_id": _derive_candidate_id(
            source_url,
            source_sha256,
            candidate["workflow_class"],
            params,
            candidate["models"],
        ),
        "source_url": source_url,
        "source_sha256": source_sha256,
        "workflow_class": candidate["workflow_class"],
        "models": candidate["models"],
        "width": candidate["width"],
        "height": candidate["height"],
        "length": candidate["length"],
        "steps": candidate["steps"],
        "source_class": "harvested",
        "status": "unverified_candidate",
        "harvested_at": harvested_at,
    }


def stage_recipe_candidates(fixture: dict[str, Any], staging_path: Path) -> StageResult:
    """Stages harvested candidates into ``staging_path`` (JSONL, append-only).

    Idempotent per ``candidate_id``: an already staged identity is skipped and
    the file is left byte-identical. A ``source_url`` already staged under a
    different ``source_sha256`` raises ``SourceMutated`` before anything is
    written — mutated sources go to re-review, never to silent update.
    """
    source_url, source_sha256, harvested_at, candidates = _validate_fixture(fixture)
    staged_rows = _load_staging(staging_path)

    for row in staged_rows:
        if row["source_url"] == source_url and row["source_sha256"] != source_sha256:
            raise SourceMutated(
                source_url=source_url,
                staged_sha256=row["source_sha256"],
                incoming_sha256=source_sha256,
            )

    staged_ids = {row["candidate_id"] for row in staged_rows}
    new_rows: list[dict[str, Any]] = []
    skipped = 0
    for candidate in candidates:
        row = _staged_row(candidate, source_url, source_sha256, harvested_at)
        if row["candidate_id"] in staged_ids:
            skipped += 1
            continue
        staged_ids.add(row["candidate_id"])
        new_rows.append(row)

    if new_rows:
        with staging_path.open("a", encoding="utf-8") as staging:
            for row in new_rows:
                staging.write(json.dumps(row) + "\n")

    return StageResult(added=len(new_rows), skipped=skipped, candidates_staged=new_rows)
