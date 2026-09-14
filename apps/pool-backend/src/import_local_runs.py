"""Import first-party lab runs (JSON overlays) into SQLite and/or derived JSONs.

Local runs survive the next `sync_pool` only if this module runs AFTER sync
(see scripts/sync-all.sh). Overlaying derived JSONs is the publish path when
the SQLite file is empty (fresh clone).

Usage:
  uv run python -m src.import_local_runs              # SQLite if present
  uv run python -m src.import_local_runs --publish    # also patch apps/web/data/derived
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from src.config import DB_PATH
from src.db import connect, migrate
from src.sync_pool import upsert_rigs, upsert_runs

HERE = Path(__file__).resolve().parent.parent
LOCAL_DIR = HERE / "local-runs"
WEB_DERIVED = HERE.parent.parent / "apps" / "web" / "data" / "derived"
WEB_NEXT_DERIVED = HERE.parent.parent / "apps" / "web-next" / "public" / "data" / "derived"


def load_bundles() -> list[dict]:
    bundles = []
    if not LOCAL_DIR.is_dir():
        return bundles
    for path in sorted(LOCAL_DIR.glob("*.json")):
        bundles.append(json.loads(path.read_text()))
    return bundles


def run_row(run: dict) -> dict:
    raw = {
        "source": "local-lab",
        "recipe": run.get("recipe"),
        "raw": run.get("raw") or {},
    }
    return {
        "id": run["id"],
        "model_slug": run["model_slug"],
        "rig_key": run["rig_key"],
        "bits": run["bits"],
        "quant": run.get("quant"),
        "engine": run.get("engine") or "llama.cpp",
        "tok_s_out": run["tok_s_out"],
        "tok_s_prefill": run.get("tok_s_prefill"),
        "ttft_ms": run.get("ttft_ms"),
        "peak_vram_gb": run.get("peak_vram_gb"),
        "context_length": run.get("context_length"),
        "batch_size": run.get("batch_size") or 1,
        "spec_decoding": run.get("spec_decoding") or 0,
        "mtp_enabled": run.get("mtp_enabled") or 0,
        "concurrency": run.get("concurrency") or 1,
        "created_at": run["created_at"],
        "raw_json": json.dumps(raw, sort_keys=True),
    }


def import_sqlite(bundles: list[dict]) -> int:
    conn = connect()
    migrate(conn)
    n = 0
    conn.execute("BEGIN")
    for bundle in bundles:
        upsert_rigs(conn, bundle["rigs"])
        existing = {row[0] for row in conn.execute("SELECT slug FROM lm_model")}
        rows = [run_row(run) for run in bundle["runs"] if run["model_slug"] in existing]
        skipped = [run["model_slug"] for run in bundle["runs"] if run["model_slug"] not in existing]
        if skipped:
            print(f"warn: skipped unknown slugs (sync first): {sorted(set(skipped))}")
        upsert_runs(conn, rows)
        n += len(rows)
    conn.execute(
        """UPDATE lm_rig SET run_count = (
            SELECT COUNT(*) FROM lm_run WHERE lm_run.rig_key = lm_rig.key
        )"""
    )
    conn.commit()
    conn.close()
    return n


def _median(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return statistics.median(clean) if clean else None


def overlay_derived(bundles: list[dict], dest: Path) -> None:
    hardware = json.loads((dest / "hardware.json").read_text())
    models = json.loads((dest / "models.json").read_text())
    pool = json.loads((dest / "pool.json").read_text())
    stats = json.loads((dest / "stats.json").read_text())

    rigs_by_key = {r["key"]: r for r in hardware["rigs"]}
    models_by_slug = {m["slug"]: m for m in models["models"]}
    cells_by_key: dict[tuple, dict] = {
        (c["rigKey"], c["modelSlug"], c["bits"]): c
        for c in pool["cells"]
        if "bits" in c and "rigKey" in c
    }

    added_runs = 0
    for bundle in bundles:
        for rig in bundle["rigs"]:
            key = rig["key"]
            if key not in rigs_by_key:
                hardware["rigs"].append(
                    {
                        "key": key,
                        "label": rig["label"],
                        "hwClass": rig["hw_class"],
                        "memGb": rig["mem_gb"],
                        "gpuCount": rig["gpu_count"],
                        "bandwidthGBs": rig.get("bandwidth_gbs"),
                        "runCount": 0,
                    }
                )
                rigs_by_key[key] = hardware["rigs"][-1]
        grouped: dict[tuple, list[dict]] = {}
        for run in bundle["runs"]:
            if run["model_slug"] not in models_by_slug:
                print(f"warn: derived skip unknown slug {run['model_slug']}")
                continue
            key = (run["rig_key"], run["model_slug"], run["bits"])
            grouped.setdefault(key, []).append(run)
            added_runs += 1
            # increment model/rig counts only the first time this cell appears
            if key not in cells_by_key:
                models_by_slug[run["model_slug"]]["runCount"] = (
                    models_by_slug[run["model_slug"]].get("runCount") or 0
                ) + 1
                if run["rig_key"] in rigs_by_key:
                    rigs_by_key[run["rig_key"]]["runCount"] = (
                        rigs_by_key[run["rig_key"]].get("runCount") or 0
                    ) + 1
        for key, runs in grouped.items():
            outs = [r["tok_s_out"] for r in runs]
            prefs = [r.get("tok_s_prefill") for r in runs]
            vrams = [r.get("peak_vram_gb") for r in runs]
            ctxs = [r.get("context_length") for r in runs if r.get("context_length")]
            # best recipe wins the published tok/s (fit vs ncmoe must not hide +50%)
            best_out = max(outs) if outs else None
            cell = {
                "rigKey": key[0],
                "modelSlug": key[1],
                "bits": key[2],
                "n": len(runs),
                "tokSOutMedian": round(best_out, 4) if best_out is not None else None,
                "tokSPrefillMedian": round(_median(prefs), 4) if _median(prefs) is not None else None,
                "ttftMsMedian": None,
                "peakVramGbMedian": _median(vrams),
                "maxContextTested": max(ctxs) if ctxs else None,
                "engines": ["llama.cpp"],
            }
            if key in cells_by_key:
                # keep the higher n / refresh numbers — first-party overlay wins
                cells_by_key[key].update(cell)
            else:
                pool["cells"].append(cell)
                cells_by_key[key] = cell

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    hardware["snapshotAt"] = stamp
    models["snapshotAt"] = stamp
    pool["snapshotAt"] = stamp
    stats["snapshotAt"] = stamp
    stats["totals"] = {
        "runs": sum(r.get("runCount") or 0 for r in hardware["rigs"]),
        "models": len(models["models"]),
        "rigs": len(hardware["rigs"]),
    }
    hardware["rigs"].sort(key=lambda r: (-(r.get("runCount") or 0), r["key"]))
    pool["cells"].sort(key=lambda c: (c.get("rigKey") or "", c.get("modelSlug") or "", c.get("bits") or 0))

    dest.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("hardware", hardware),
        ("models", models),
        ("pool", pool),
        ("stats", stats),
    ):
        (dest / f"{name}.json").write_text(json.dumps(payload, indent=1) + "\n")
    print(f"published overlay -> {dest} (+{added_runs} run rows)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--sqlite-only", action="store_true")
    args = parser.parse_args()
    bundles = load_bundles()
    if not bundles:
        print("no local-run bundles")
        return
    db = Path(DB_PATH)
    if db.exists() or args.sqlite_only:
        n = import_sqlite(bundles)
        print(f"sqlite imported: {n} runs")
    elif not args.publish:
        print(f"no {DB_PATH}; pass --publish to overlay derived JSONs")
    if args.publish:
        overlay_derived(bundles, WEB_DERIVED)
        next_pool = WEB_NEXT_DERIVED / "pool.json"
        if next_pool.is_file():
            sample = json.loads(next_pool.read_text())
            cells = sample.get("cells") or []
            if cells and "bits" in cells[0]:
                overlay_derived(bundles, WEB_NEXT_DERIVED)
            else:
                print(f"skip {WEB_NEXT_DERIVED}: pool cells lack 'bits' (different schema)")


if __name__ == "__main__":
    main()
