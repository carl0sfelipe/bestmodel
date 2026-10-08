"""Best model per intent and VRAM (S49, contract hq/contracts/model-pick-v1).

Reads the published pool snapshot (apps/web/data/derived) and the intent
catalog. Ranking: confidence, then pool eval score, then speed. Pool cells are community reports, so a cell is never labelled
``measured``: that class is reserved for signed runs. An intent with no cell
answers ``picks: []`` and ``confidence_floor: "no data yet"``; nothing is
invented to fill it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONTRACT = "model-pick-v1"
DEFAULT_LIMIT = 5
MAX_LIMIT = 20

# Contract intent name -> intent-catalog id.
INTENTS = {
    "chat": "chat",
    "image.generate": "image",
    "vision": "vision",
    "audio": "audio",
}

CONFIDENCE_ORDER = ("measured", "reported", "extrapolated", "formula", "no data yet")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SNAPSHOT_DIR = _REPO_ROOT / "apps" / "web" / "data" / "derived"
_CATALOG = _REPO_ROOT / "packages" / "intent-catalog" / "catalog.json"

# Catalog metric field -> (pool cell field, contract metric name).
_CELL_METRICS = {
    "tokSOutMedian": ("tokSOutMedian", "decode_tok_s"),
}


class PickError(ValueError):
    """Invalid request; the message lists the valid values."""


def snapshot_dir() -> Path:
    return Path(os.environ.get("BESTMODEL_POOL_SNAPSHOT_DIR") or _SNAPSHOT_DIR)


def catalog_path() -> Path:
    return Path(os.environ.get("BESTMODEL_INTENT_CATALOG") or _CATALOG)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_models(intent: str, vram_gib: float, gpu: str, limit: int | None = None) -> dict[str, Any]:
    if intent not in INTENTS:
        raise PickError(f"unknown intent {intent!r}; valid: {sorted(INTENTS)}")
    if vram_gib <= 0:
        raise PickError("vram_gib must be > 0")
    directory = snapshot_dir()
    pool = _read(directory / "pool.json")
    rigs = {row["key"] for row in _read(directory / "hardware.json")["rigs"]}
    if gpu not in rigs:
        raise PickError(f"unknown gpu {gpu!r}; use a rig key from /hardware?as=agent, e.g. 'rtx-3090-24gb'")
    category = INTENTS[intent]
    intent_row = next(row for row in _read(catalog_path())["intents"] if row["id"] == category)
    models = {row["slug"]: row for row in _read(directory / "models.json")["models"]}
    picks = _picks(pool["cells"], models, category, intent_row["metric"], vram_gib, gpu)
    safe_limit = max(1, min(limit or DEFAULT_LIMIT, MAX_LIMIT))
    body: dict[str, Any] = {
        "contract": CONTRACT,
        "intent": intent,
        "gpu": gpu,
        "vram_gib": vram_gib,
        "snapshot_at": pool["snapshotAt"],
        "picks": picks[:safe_limit],
    }
    if not picks:
        body["confidence_floor"] = "no data yet"
    return body


def _picks(cells, models, category, metric, vram_gib, gpu) -> list[dict[str, Any]]:
    mapping = _CELL_METRICS.get(metric["field"])
    if mapping is None:
        # The snapshot carries no cell field for this metric yet.
        return []
    cell_field, metric_name = mapping
    picks = []
    for cell in cells:
        model = models.get(cell["modelSlug"])
        if cell["rigKey"] != gpu or model is None or model.get("category") != category:
            continue
        peak = cell.get("peakVramGbMedian")
        value = cell.get(cell_field)
        # Unknown peak VRAM cannot be shown to fit; a missing metric is not a pick.
        if peak is None or value is None or peak > vram_gib:
            continue
        picks.append(_pick(cell, model, peak, metric_name, value))
    picks.sort(key=_rank)
    return picks


def _rank(pick: dict[str, Any]) -> tuple[Any, ...]:
    # Best = most trustworthy, then highest pool eval score, then fastest.
    # A model without an eval score ranks after every scored one.
    score = pick["quality"]["eval_score"]
    return (CONFIDENCE_ORDER.index(pick["confidence"]), score is None, -(score or 0.0), -pick["perf"]["value"])


def _pick(cell, model, peak, metric_name, value) -> dict[str, Any]:
    return {
        "model_id": model["slug"],
        "hf_repo": model.get("hfId"),
        "quant": None,
        "bits": cell.get("bits"),
        "runtime": (cell.get("engines") or [None])[0],
        "vram_peak_gib": peak,
        "perf": {"metric": metric_name, "value": value, "concurrency": 1},
        "quality": _quality(model),
        "confidence": _confidence(model),
        "evidence": {
            "n_runs": cell["n"],
            "source_class": model.get("sourceClass"),
            "source": f"/m/{model['slug']}?as=agent",
        },
    }


def _quality(model: dict[str, Any]) -> dict[str, Any]:
    score = model.get("evalScore") or {}
    return {"eval_score": score.get("score"), "n_evals": score.get("count")}


def _confidence(model: dict[str, Any]) -> str:
    # Only community reports reach the snapshot today; signed runs live in the
    # leaderboard. Anything unrecognized is downgraded, never promoted.
    return "reported" if model.get("sourceClass") == "community_reported" else "no data yet"
