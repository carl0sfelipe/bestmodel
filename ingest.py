#!/usr/bin/env python3
# ingest.py — Fase C: results.jsonl (runs cruas da sweep) → células agregadas
# em public/data/derived/pool.json + entradas em models.json.
# Formato da célula = o que o metricOf de lib/engine.ts consome (campos FLAT):
#   category, imagesPerSec|audioXReal|rtf|videoFramesPerSec (mediana), steps,
#   resolution, durationS, pipeline, precision, peakVramGb (mediana), n.
# Agregação: mediana por (category, pipeline, precision, steps, resolution).
# Honestidade: n real; basis vem de n (>=3 measured) — o site decide pelo n.
# music is the text-to-music intent of the audio modality (same ×real/RTF
# path as Whisper STT); never decode_tok_s.
import json, statistics, sys, time

SRC = sys.argv[1] if len(sys.argv) > 1 else "results.jsonl"

runs = [json.loads(l) for l in open(SRC) if l.strip()]
print(f"runs cruas: {len(runs)}")

def metric_key(r):
    for k in ("imagesPerSec", "audioXReal", "rtf", "videoFramesPerSec"):
        if r.get(k) is not None:
            return k
    return None

groups = {}
for r in runs:
    key = (r["category"], r["pipeline"], r.get("precision"), r.get("steps"), r.get("resolution"), r.get("durationS"))
    groups.setdefault(key, []).append(r)

def _median(rows, key, digits=4):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return round(statistics.median(vals), digits) if vals else None

new_cells, new_models = [], []
for (cat, pipe, prec, steps, res, dur), rs in sorted(groups.items()):
    mk = metric_key(rs[0])
    assert mk, f"run sem métrica: {rs[0]}"
    cell = {
        "rigKey": rs[0]["rigKey"],
        "modelSlug": pipe,
        "category": cat,
        "pipeline": pipe,
        mk: _median(rs, mk),
        "peakVramGb": _median(rs, "peakVramGb"),
        "n": len(rs),
        "hw": rs[0]["hw"],
    }
    if prec is not None: cell["precision"] = prec
    timestamps = [r["ts"] for r in rs if r.get("ts")]
    if timestamps: cell["measuredAt"] = max(timestamps)
    if steps is not None: cell["steps"] = steps
    if res is not None: cell["resolution"] = res
    if dur is not None: cell["durationS"] = dur
    wall = _median(rs, "wallS")
    if wall is not None: cell["wallS"] = wall
    samples = _median(rs, "samples", digits=0)
    if samples is not None: cell["samples"] = int(samples)
    new_cells.append(cell)
    model = {
        "slug": pipe,
        "displayName": rs[0].get("displayName") or pipe,
        "category": cat,
        "sourceClass": "owner_measured",
        "family": rs[0].get("family") or cat,
        "runCount": len(rs),
    }
    if rs[0].get("hfId"): model["hfId"] = rs[0]["hfId"]
    new_models.append(model)
    print(f"  + {cat:5s} {pipe:32s} n={len(rs):2d} {cell[mk]} ({mk}) vram={cell['peakVramGb']}GB")

POOL = "apps/web-next/public/data/derived/pool.json"
MODELS = "apps/web-next/public/data/derived/models.json"
HARDWARE = "apps/web-next/public/data/derived/hardware.json"
STATS = "apps/web-next/public/data/derived/stats.json"

def cell_key(c):
    return (c.get("rigKey"), c.get("modelSlug"), c.get("category"), c.get("bits"), c.get("durationS"))

pool = json.load(open(POOL))
fresh = {cell_key(c) for c in new_cells}
pool["cells"] = [c for c in pool["cells"] if cell_key(c) not in fresh]
pool["cells"].extend(new_cells)
# No timestamp on the runs → do not restamp the text-pool snapshot.
if any(c.get("measuredAt") for c in new_cells):
    pool["snapshotAt"] = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
json.dump(pool, open(POOL, "w"), ensure_ascii=False, indent=1)
open(POOL, "a").write("\n")

models = json.load(open(MODELS))
by_slug = {m["slug"]: m for m in models["models"]}
added = []
for model in new_models:
    runs_n = sum(c["n"] for c in pool["cells"] if c.get("modelSlug") == model["slug"] and c.get("category") == model["category"])
    model["runCount"] = runs_n or model["runCount"]
    if model["slug"] in by_slug:
        by_slug[model["slug"]].update(model)
    else:
        models["models"].append(model)
        by_slug[model["slug"]] = model
        added.append(model)
if any(c.get("measuredAt") for c in new_cells):
    models["snapshotAt"] = pool["snapshotAt"]
json.dump(models, open(MODELS, "w"), ensure_ascii=False, indent=1)
open(MODELS, "a").write("\n")

hardware = json.load(open(HARDWARE))
by_rig = {r["key"]: r for r in hardware["rigs"]}
for sample in runs:
    key = sample.get("rigKey")
    if not key or key in by_rig:
        continue
    provider = sample.get("provider") or ""
    gpu = sample.get("gpuName") or key
    label = f"{gpu} (modal)" if "modal" in provider else gpu
    by_rig[key] = {
        "key": key,
        "label": label,
        "hwClass": "DISCRETE_GPU",
        "memGb": sample.get("vramTotalGb"),
        "gpuCount": 1,
        "bandwidthGBs": None,
        "runCount": 0,
    }
    hardware["rigs"].append(by_rig[key])
for rig in hardware["rigs"]:
    ours = [c for c in new_cells if c["rigKey"] == rig["key"]]
    if ours:
        rig["runCount"] = sum(c["n"] for c in pool["cells"] if c.get("rigKey") == rig["key"] and c.get("hw"))
json.dump(hardware, open(HARDWARE, "w"), ensure_ascii=False, indent=1)
open(HARDWARE, "a").write("\n")

stats = json.load(open(STATS))
hw_labels = sorted({c["hw"] for c in new_cells if c.get("hw")})
block = {
    "cells": len(new_cells),
    "runs": len(runs),
    "hw": hw_labels[0] if len(hw_labels) == 1 else (hw_labels or ["RTX 3090 24GB (vast.ai, overnight 2026-08-31)"])[0],
    "categories": sorted({c["category"] for c in new_cells}),
}
if new_cells and all(c["category"] == "music" for c in new_cells):
    # Music anchor block only. Do not relabel this file as the 3090 overnight sweep.
    stats["musicAnchors"] = block
else:
    if not hw_labels:
        block["hw"] = "RTX 3090 24GB (vast.ai, overnight 2026-08-31)"
    stats["multimodal"] = block
    stats["snapshotAt"] = pool["snapshotAt"]
json.dump(stats, open(STATS, "w"), ensure_ascii=False, indent=1)
open(STATS, "a").write("\n")
print(f"ingest ok: +{len(new_cells)} células, +{len(added)} modelos novos")
