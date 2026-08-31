#!/usr/bin/env python3
# ingest.py — Fase C: results.jsonl (runs cruas da sweep) → células agregadas
# em public/data/derived/pool.json + entradas em models.json.
# Formato da célula = o que o metricOf de lib/engine.ts consome (campos FLAT):
#   category, imagesPerSec|audioXReal|videoFramesPerSec (mediana), steps,
#   resolution, durationS, pipeline, precision, peakVramGb (mediana), n.
# Agregação: mediana por (category, pipeline, precision, steps, resolution).
# Honestidade: n real; basis vem de n (>=3 measured) — o site decide pelo n.
import json, statistics, sys, time

SRC = sys.argv[1] if len(sys.argv) > 1 else "results.jsonl"

runs = [json.loads(l) for l in open(SRC) if l.strip()]
print(f"runs cruas: {len(runs)}")

def metric_key(r):
    for k in ("imagesPerSec", "audioXReal", "videoFramesPerSec"):
        if r.get(k) is not None:
            return k
    return None

groups = {}
for r in runs:
    key = (r["category"], r["pipeline"], r.get("precision"), r.get("steps"), r.get("resolution"), r.get("durationS"))
    groups.setdefault(key, []).append(r)

new_cells, new_models = [], []
for (cat, pipe, prec, steps, res, dur), rs in sorted(groups.items()):
    mk = metric_key(rs[0])
    assert mk, f"run sem métrica: {rs[0]}"
    cell = {
        "rigKey": rs[0]["rigKey"],
        "modelSlug": pipe,
        "category": cat,
        "pipeline": pipe,
        "precision": prec,
        mk: round(statistics.median([r[mk] for r in rs]), 2),
        "peakVramGb": round(statistics.median([r["peakVramGb"] for r in rs]), 2),
        "n": len(rs),
        "measuredAt": max(r["ts"] for r in rs),
        "hw": rs[0]["hw"],
    }
    if steps is not None: cell["steps"] = steps
    if res is not None: cell["resolution"] = res
    if dur is not None: cell["durationS"] = dur
    new_cells.append(cell)
    new_models.append({
        "slug": pipe,
        "displayName": pipe,
        "category": cat,
        "sourceClass": "owner_measured",
        "family": cat,
        "runCount": len(rs),
    })
    print(f"  + {cat:5s} {pipe:32s} n={len(rs):2d} {cell[mk]} ({mk}) vram={cell['peakVramGb']}GB")

POOL = "apps/web-next/public/data/derived/pool.json"
MODELS = "apps/web-next/public/data/derived/models.json"

pool = json.load(open(POOL))
pool["cells"].extend(new_cells)
pool["snapshotAt"] = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
json.dump(pool, open(POOL, "w"), ensure_ascii=False, indent=1)

models = json.load(open(MODELS))
existing = {m["slug"] for m in models["models"]}
added = [m for m in new_models if m["slug"] not in existing]
models["models"].extend(added)
models["snapshotAt"] = pool["snapshotAt"]
json.dump(models, open(MODELS, "w"), ensure_ascii=False, indent=1)

stats = json.load(open("apps/web-next/public/data/derived/stats.json"))
stats["snapshotAt"] = pool["snapshotAt"]
stats["multimodal"] = {
    "cells": len(new_cells),
    "runs": len(runs),
    "hw": "RTX 3090 24GB (vast.ai, overnight 2026-08-31)",
    "categories": sorted({c["category"] for c in new_cells}),
}
json.dump(stats, open("apps/web-next/public/data/derived/stats.json", "w"), ensure_ascii=False, indent=1)
print(f"ingest ok: +{len(new_cells)} células, +{len(added)} modelos novos")
