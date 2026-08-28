"""Deterministic harvester framework (Epic 4, Story 4.1).

Turns a fixture (structured extract fetched by the scripts of Stories 4.2/4.3)
into staged benchmark cells: hashes the fixture bytes, derives a stable
``cell_id`` per cell, and appends cells to a JSONL staging file. Staging is
never production — every cell leaves here with ``source_class="harvested"``
and ``status="unverified"``; the review queue that promotes cells is Story
4.4. Re-running the same fixture is a no-op (no duplicated cells), and a
source whose content changed under the same ``source_url`` is rejected with
``SourceMutated`` instead of being silently updated.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

REQUIRED_CELL_FIELDS = ("gpu_model_id", "model_release_id", "metric", "value", "unit")


class SourceMutated(Exception):
    """An identity already staged under ``source_url`` arrived with a different content hash."""

    def __init__(self, source_url: str, staged_sha256: str, incoming_sha256: str) -> None:
        self.source_url = source_url
        self.staged_sha256 = staged_sha256
        self.incoming_sha256 = incoming_sha256
        super().__init__(
            f"source content changed under the same source_url {source_url!r} "
            f"(staged_sha256={staged_sha256}, incoming_sha256={incoming_sha256})"
        )


@dataclass
class HarvestResult:
    added: int
    skipped: int
    cells_staged: list[dict[str, Any]]


def _parse_fixture(fixture_path: Path) -> tuple[dict[str, Any], str]:
    raw = fixture_path.read_bytes()
    source_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"fixture is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("fixture field 'source_url' is missing: root is not a JSON object")
    if not isinstance(payload.get("source_url"), str):
        raise ValueError("fixture field 'source_url' is missing or not a string")
    if not isinstance(payload.get("cells"), list):
        raise ValueError("fixture field 'cells' is missing or not a list")
    for index, cell in enumerate(payload["cells"]):
        _validate_cell(cell, index)
    return payload, source_sha256


def _validate_cell(cell: Any, index: int) -> None:
    if not isinstance(cell, dict):
        raise ValueError(f"fixture field 'cells[{index}]' is not an object")
    for field in REQUIRED_CELL_FIELDS:
        if field not in cell:
            raise ValueError(f"fixture field 'cells[{index}].{field}' is missing")


def _identity(
    source_url: str, gpu: str, model: str, recipe: str | None, metric: str
) -> tuple[str, str, str, str | None, str]:
    return (source_url, gpu, model, recipe, metric)


def _derive_cell_id(
    source_url: str, source_sha256: str, gpu: str, model: str, recipe: str | None, metric: str
) -> str:
    recipe_key = recipe if recipe is not None else ""
    key = f"{source_url}|{source_sha256}|{gpu}|{model}|{recipe_key}|{metric}"
    return str(uuid.uuid5(UUID_NAMESPACE, key))


def _load_staging(staging_path: Path) -> list[dict[str, Any]]:
    if not staging_path.exists():
        return []
    rows = []
    for line in staging_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _staged_row(
    cell: dict[str, Any], source_url: str, source_sha256: str, harvested_at: Any
) -> dict[str, Any]:
    gpu = cell["gpu_model_id"]
    model = cell["model_release_id"]
    recipe = cell.get("recipe_id")
    metric = cell["metric"]
    return {
        "cell_id": _derive_cell_id(source_url, source_sha256, gpu, model, recipe, metric),
        "source_url": source_url,
        "source_sha256": source_sha256,
        "gpu_model_id": gpu,
        "model_release_id": model,
        "recipe_id": recipe,
        "metric": metric,
        "value": cell["value"],
        "unit": cell["unit"],
        "source_class": "harvested",
        "status": "unverified",
        "harvested_at": harvested_at,
    }


def harvest(fixture_path: Path, staging_path: Path) -> HarvestResult:
    payload, source_sha256 = _parse_fixture(fixture_path)
    source_url: str = payload["source_url"]
    staged_by_identity: dict[tuple[str, str, str, str | None, str], dict[str, Any]] = {}
    for row in _load_staging(staging_path):
        identity = _identity(
            row["source_url"],
            row["gpu_model_id"],
            row["model_release_id"],
            row.get("recipe_id"),
            row["metric"],
        )
        staged_by_identity.setdefault(identity, row)

    new_cells: list[dict[str, Any]] = []
    skipped = 0
    for cell in payload["cells"]:
        identity = _identity(
            source_url,
            cell["gpu_model_id"],
            cell["model_release_id"],
            cell.get("recipe_id"),
            cell["metric"],
        )
        existing = staged_by_identity.get(identity)
        if existing is not None:
            if existing["source_sha256"] != source_sha256:
                raise SourceMutated(
                    source_url=source_url,
                    staged_sha256=existing["source_sha256"],
                    incoming_sha256=source_sha256,
                )
            skipped += 1
            continue
        staged = _staged_row(cell, source_url, source_sha256, payload.get("harvested_at"))
        staged_by_identity[identity] = staged
        new_cells.append(staged)

    with staging_path.open("a", encoding="utf-8") as staging:
        for staged in new_cells:
            staging.write(json.dumps(staged) + "\n")

    return HarvestResult(added=len(new_cells), skipped=skipped, cells_staged=new_cells)
