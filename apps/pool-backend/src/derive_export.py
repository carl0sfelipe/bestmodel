"""Derived export: SQLite -> out/derived/{hardware,models,pool,stats}.json.

Replicates the web pack S2 aggregation rules (CONTRATO web §4/§6) with the
SQLite pool as source, excluding runs flagged 'impossible' by S3 (CONTRATO
backend §6). Aggregation is SQL GROUP BY + Python post-processing; medians,
sorting, key order and JS-style number formatting keep the output
deterministic byte-for-byte across runs without a new sync.

Executable via `uv run python -m src.derive_export [--publish]`. --publish
also copies the four files to ../apps/web/data/derived/ and drops a
marker file so `check.py derived` can assert publish byte-identity.
"""

import json
import os
import shutil
import sqlite3
import sys
from math import floor
from typing import Any

from src.config import DB_PATH
from src.db import connect, migrate

OUT_DIR = "out/derived"
WEB_DERIVED_DIR = "../apps/web/data/derived"
PUBLISH_MARKER = ".published"

CLEAN_EXISTS = """EXISTS (SELECT 1 FROM plausibility_flag p
                           WHERE p.run_id = r.id AND p.verdict != 'impossible')"""

RIGS_SQL = f"""
    SELECT g.key, g.label, g.hw_class, g.mem_gb, g.gpu_count, g.bandwidth_gbs,
           COUNT(r.id) AS run_count
    FROM lm_rig g
    JOIN lm_run r ON r.rig_key = g.key
    WHERE {CLEAN_EXISTS}
    GROUP BY g.key
"""

MODELS_SQL = f"""
    SELECT m.slug, m.hf_id, m.display_name, m.family, m.params_b,
           m.active_params_b, m.is_moe, m.category, m.eval_score,
           COUNT(r.id) AS run_count
    FROM lm_model m
    JOIN lm_run r ON r.model_slug = m.slug
    WHERE {CLEAN_EXISTS}
    GROUP BY m.slug
"""

TOKS_SQL = f"""
    SELECT r.model_slug, r.tok_s_out
    FROM lm_run r
    WHERE {CLEAN_EXISTS}
"""

SS_SQL = f"""
    SELECT r.model_slug, r.bits, r.peak_vram_gb, r.context_length
    FROM lm_run r
    WHERE {CLEAN_EXISTS}
      AND COALESCE(r.batch_size, 1) <= 1 AND COALESCE(r.concurrency, 1) <= 1
"""

CELLS_SQL = f"""
    SELECT r.rig_key, r.model_slug, r.bits, r.tok_s_out, r.tok_s_prefill,
           r.ttft_ms, r.peak_vram_gb, r.context_length, r.engine
    FROM lm_run r
    WHERE {CLEAN_EXISTS}
      AND r.bits IS NOT NULL
      AND COALESCE(r.batch_size, 1) <= 1 AND COALESCE(r.concurrency, 1) <= 1
"""

EXCLUDED_SQL = """SELECT COUNT(*) FROM lm_run r
                  JOIN plausibility_flag p ON p.run_id = r.id
                  WHERE p.verdict = 'impossible' AND r.bits IS NOT NULL"""
SUSPICIOUS_SQL = """SELECT COUNT(*) FROM lm_run r
                    JOIN plausibility_flag p ON p.run_id = r.id
                    WHERE p.verdict = 'suspicious'"""
COMPUTED_AT_SQL = "SELECT MAX(computed_at) FROM plausibility_flag"
SNAPSHOT_SQL = "SELECT value FROM sync_meta WHERE key = 'last_sync_at'"


def round2(value: float) -> float:
    """JS Math.round semantics at 2 decimals (round half away from zero)."""
    return floor(value * 100 + 0.5) / 100


def median(values: list[float]) -> float | None:
    """JS-style median: sorted, middle (even: mean of middle pair), rounded."""
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round2(ordered[mid])
    return round2((ordered[mid - 1] + ordered[mid]) / 2)


def _js_intify(value: Any) -> Any:
    """Recursively render integral floats as ints, matching JS JSON.stringify."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: _js_intify(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_js_intify(item) for item in value]
    return value


def snapshot_at(conn: sqlite3.Connection) -> str:
    """Export timestamp: the sync's own last_sync_at, never 'now'."""
    row = conn.execute(SNAPSHOT_SQL).fetchone()
    if row is None:
        raise RuntimeError("sync_meta has no last_sync_at; run src.sync_pool first")
    return row["value"]


def build_rigs(conn: sqlite3.Connection) -> list[dict]:
    """Rigs over clean (non-impossible) runs, runCount desc then key asc."""
    rigs = [
        {
            "key": row["key"],
            "label": row["label"],
            "hwClass": row["hw_class"],
            "memGb": row["mem_gb"],
            "gpuCount": row["gpu_count"],
            "bandwidthGBs": row["bandwidth_gbs"],
            "runCount": row["run_count"],
        }
        for row in conn.execute(RIGS_SQL)
    ]
    rigs.sort(key=lambda rig: (-rig["runCount"], rig["key"]))
    return rigs


def _vram_samples(conn: sqlite3.Connection) -> dict[str, dict[int, list[float]]]:
    """peakVramGb per (model, bits) over clean single-stream runs."""
    samples: dict[str, dict[int, list[float]]] = {}
    for row in conn.execute(SS_SQL):
        if row["bits"] is None or not row["peak_vram_gb"] or row["peak_vram_gb"] <= 0:
            continue
        per_bits = samples.setdefault(row["model_slug"], {})
        per_bits.setdefault(row["bits"], []).append(row["peak_vram_gb"])
    return samples


def build_models(conn: sqlite3.Connection) -> list[dict]:
    """DerivedModel list; medianTokS over clean runs, VRAM/ctx over single-stream."""
    tok_s: dict[str, list[float]] = {}
    for row in conn.execute(TOKS_SQL):
        tok_s.setdefault(row["model_slug"], []).append(row["tok_s_out"])
    vram = _vram_samples(conn)
    context: dict[str, list[int]] = {}
    for row in conn.execute(SS_SQL):
        if row["context_length"] is not None:
            context.setdefault(row["model_slug"], []).append(row["context_length"])

    models = []
    for row in conn.execute(MODELS_SQL):
        slug = row["slug"]
        vram_measured = {
            str(bits): {"gb": median(samples), "n": len(samples)}
            for bits, samples in sorted(vram.get(slug, {}).items())
        }
        contexts = context.get(slug, [])
        models.append(
            {
                "slug": slug,
                "hfId": row["hf_id"],
                "displayName": row["display_name"],
                "family": row["family"],
                "paramsB": row["params_b"],
                "activeParamsB": row["active_params_b"],
                "isMoE": bool(row["is_moe"]),
                "category": row["category"],
                "runCount": row["run_count"],
                "medianTokS": median(tok_s.get(slug, [])),
                "evalScore": row["eval_score"],
                "vramMeasuredGb": vram_measured,
                "maxContextTested": max(contexts) if contexts else None,
            }
        )
    models.sort(key=lambda model: (-model["runCount"], model["slug"]))
    return models


def build_cells(conn: sqlite3.Connection) -> list[dict]:
    """Pool cells over clean single-stream runs, keyed (rig, model, bits)."""
    grouped: dict[tuple[str, str, int], dict] = {}
    for row in conn.execute(CELLS_SQL):
        key = (row["rig_key"], row["model_slug"], row["bits"])
        cell = grouped.get(key)
        if cell is None:
            cell = {
                "_out": [], "_prefill": [], "_ttft": [],
                "_vram": [], "_ctx": [], "_engines": set(),
            }
            grouped[key] = cell
        cell["_out"].append(row["tok_s_out"])
        if row["tok_s_prefill"] and row["tok_s_prefill"] > 0:
            cell["_prefill"].append(row["tok_s_prefill"])
        if row["ttft_ms"] and row["ttft_ms"] > 0:
            cell["_ttft"].append(row["ttft_ms"])
        if row["peak_vram_gb"] and row["peak_vram_gb"] > 0:
            cell["_vram"].append(row["peak_vram_gb"])
        if row["context_length"] is not None:
            cell["_ctx"].append(row["context_length"])
        if row["engine"]:
            cell["_engines"].add(row["engine"])

    cells = []
    for (rig_key, model_slug, bits), cell in grouped.items():
        cells.append(
            {
                "rigKey": rig_key,
                "modelSlug": model_slug,
                "bits": bits,
                "n": len(cell["_out"]),
                "tokSOutMedian": median(cell["_out"]),
                "tokSPrefillMedian": median(cell["_prefill"]),
                "ttftMsMedian": median(cell["_ttft"]),
                "peakVramGbMedian": median(cell["_vram"]),
                "maxContextTested": max(cell["_ctx"]) if cell["_ctx"] else None,
                "engines": sorted(cell["_engines"]),
            }
        )
    cells.sort(key=lambda cell: (cell["rigKey"], cell["modelSlug"], cell["bits"]))
    return cells


def build_stats(
    conn: sqlite3.Connection, rigs: list[dict], models: list[dict]
) -> dict:
    """Envelope totals, top rigs/models, and the additive curation block."""
    return {
        "snapshotAt": snapshot_at(conn),
        "totals": {
            "runs": sum(rig["runCount"] for rig in rigs),
            "models": len(models),
            "rigs": len(rigs),
        },
        "topRigs": [
            {"key": rig["key"], "label": rig["label"], "runCount": rig["runCount"]}
            for rig in rigs[:8]
        ],
        "topModels": [
            {"slug": model["slug"], "displayName": model["displayName"],
             "runCount": model["runCount"]}
            for model in models[:10]
        ],
        "curation": {
            "excludedImpossible": conn.execute(EXCLUDED_SQL).fetchone()[0],
            "flaggedSuspicious": conn.execute(SUSPICIOUS_SQL).fetchone()[0],
            "computedAt": conn.execute(COMPUTED_AT_SQL).fetchone()[0],
        },
    }


def export_payloads(conn: sqlite3.Connection) -> dict[str, dict]:
    """The four derived documents keyed by output name (byte-deterministic)."""
    stamp = snapshot_at(conn)
    rigs = build_rigs(conn)
    models = build_models(conn)
    cells = build_cells(conn)
    return {
        "hardware": {"snapshotAt": stamp, "rigs": rigs},
        "models": {"snapshotAt": stamp, "models": models},
        "pool": {"snapshotAt": stamp, "cells": cells},
        "stats": build_stats(conn, rigs, models),
    }


def write_outputs(payloads: dict[str, dict]) -> None:
    """Write the four JSONs into out/derived/ (JS-style formatting)."""
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, payload in payloads.items():
        with open(f"{OUT_DIR}/{name}.json", "w", encoding="utf-8") as handle:
            json.dump(_js_intify(payload), handle, indent=1)


def publish(payloads: dict[str, dict]) -> None:
    """Copy the four JSONs to the web pack and mark them as published."""
    os.makedirs(WEB_DERIVED_DIR, exist_ok=True)
    for name in payloads:
        shutil.copyfile(f"{OUT_DIR}/{name}.json", f"{WEB_DERIVED_DIR}/{name}.json")
    with open(f"{OUT_DIR}/{PUBLISH_MARKER}", "w", encoding="utf-8") as handle:
        handle.write("1\n")


def main() -> None:
    publish_enabled = "--publish" in sys.argv[1:]
    conn = connect()
    migrate(conn)
    try:
        payloads = export_payloads(conn)
        write_outputs(payloads)
        if publish_enabled:
            publish(payloads)
    finally:
        conn.close()
    cells = len(payloads["pool"]["cells"])
    print(
        f"derived: {len(payloads['hardware']['rigs'])} rigs, "
        f"{len(payloads['models']['models'])} models, {cells} cells "
        f"(published={publish_enabled})"
    )


if __name__ == "__main__":
    main()
