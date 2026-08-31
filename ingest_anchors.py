#!/usr/bin/env python3
"""ingest_anchors.py — âncoras de nuvem (Modal) → pool.json/models.json/hardware.json.

Entradas: JSONL de runs cruas (multimodal, formato results.jsonl) e JSONL de
reps de texto (kind=text, 1 linha por rep). Agrega com mediana, faz DEDUPE por
chave (rigKey, modelSlug, categoria, bits) — substitui célula nossa mais velha,
nunca duplica (incidente do ingest 2x) — e atualiza runCount de rigs e modelos.

Uso: python3 ingest_anchors.py runs-multimodal.jsonl [reps-texto.jsonl ...]
"""
import json, statistics, sys, time

BASE = "apps/web-next/public/data/derived"
mm_rows, text_rows = [], []
for path in sys.argv[1:]:
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        (text_rows if r.get("kind") == "text" else mm_rows).append(r)

def metric_key(r):
    for k in ("imagesPerSec", "audioXReal", "videoFramesPerSec"):
        if r.get(k) is not None:
            return k
    return None

def median(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return round(statistics.median(vals), 2) if vals else None

pool = json.load(open(f"{BASE}/pool.json"))
models = json.load(open(f"{BASE}/models.json"))
hardware = json.load(open(f"{BASE}/hardware.json"))
stats = json.load(open(f"{BASE}/stats.json"))

def cell_key(c):
    return (c["rigKey"], c["modelSlug"], c.get("category"), c.get("bits"))

# ---------- células multimodais (mesma agregação do ingest.py) ----------
mm_cells = []
groups = {}
for r in mm_rows:
    key = (r["category"], r["pipeline"], r.get("precision"), r.get("steps"),
           r.get("resolution"), r.get("durationS"))
    groups.setdefault(key, []).append(r)
for (cat, pipe, prec, steps, res, dur), rs in sorted(groups.items()):
    mk = metric_key(rs[0])
    assert mk, f"run sem métrica: {rs[0]}"
    cell = {
        "rigKey": rs[0]["rigKey"], "modelSlug": pipe, "category": cat,
        "pipeline": pipe, "precision": prec, mk: median(rs, mk),
        "peakVramGb": median(rs, "peakVramGb"), "n": len(rs),
        "measuredAt": max(r["ts"] for r in rs), "hw": rs[0]["hw"],
    }
    if steps is not None: cell["steps"] = steps
    if res is not None: cell["resolution"] = res
    if dur is not None: cell["durationS"] = dur
    mm_cells.append(cell)

# ---------- células de texto (1 célula por slug×rig, mediana das reps) ----------
tx_cells = {}
for r in text_rows:
    key = (r["rigKey"], r["modelSlug"])
    tx_cells.setdefault(key, []).append(r)
for (rig, slug), rs in tx_cells.items():
    mm_cells.append({
        "rigKey": rig, "modelSlug": slug, "bits": rs[0].get("bits", 4),
        "n": len(rs),
        "tokSOutMedian": median(rs, "tokSOutMedian"),
        "tokSPrefillMedian": median(rs, "tokSPrefillMedian"),
        "ttftMsMedian": median(rs, "ttftMsMedian"),
        "peakVramGbMedian": median(rs, "peakVramGb"),
        "maxContextTested": max(r.get("maxContextTested") or 0 for r in rs) or None,
        "engines": sorted({e for r in rs for e in r.get("engines", [])}),
        "measuredAt": max(r["ts"] for r in rs), "hw": rs[0]["hw"],
    })

# ---------- merge com dedupe ----------
pool["cells"] = [c for c in pool["cells"] if cell_key(c) not in {cell_key(n) for n in mm_cells}]
pool["cells"].extend(mm_cells)
pool["snapshotAt"] = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

# ---------- modelos novos ----------
new_models = {
    "whisper-large-v3": {
        "hfId": "openai/whisper-large-v3", "displayName": "Whisper Large v3",
        "family": "Whisper", "paramsB": 1.54, "category": "audio"},
    "unsloth-llama-3-1-8b-instruct-gguf": {
        "hfId": "unsloth/Llama-3.1-8B-Instruct-GGUF",
        "displayName": "Llama 3.1 8B Instruct GGUF", "family": "Llama",
        "paramsB": 8, "category": "chat"},
    "unsloth-qwen2-5-coder-7b-instruct-gguf": {
        "hfId": "unsloth/Qwen2.5-Coder-7B-Instruct-GGUF",
        "displayName": "Qwen2.5 Coder 7B Instruct GGUF", "family": "Qwen",
        "paramsB": 7, "category": "code"},
}
by_slug = {m["slug"]: m for m in models["models"]}
for slug, meta in new_models.items():
    entry = {"slug": slug, **meta, "isMoE": False,
             "sourceClass": "owner_measured"}
    if slug in by_slug:
        by_slug[slug].update(entry)
    else:
        models["models"].append(entry)
        by_slug[slug] = entry
for slug, m in by_slug.items():
    runs = sum(c["n"] for c in pool["cells"] if c["modelSlug"] == slug)
    if runs and m.get("sourceClass") == "owner_measured":
        m["runCount"] = runs
models["snapshotAt"] = pool["snapshotAt"]

# ---------- rigs (rótulo/dados de hardware + runCount recontado) ----------
RIGS = {
    "l4-24gb": {"label": "L4 24GB (modal)", "hwClass": "DISCRETE_GPU",
                "memGb": 24, "gpuCount": 1, "bandwidthGBs": 300},
    "a10-24gb": {"label": "A10 24GB (modal)", "hwClass": "DISCRETE_GPU",
                 "memGb": 24, "gpuCount": 1, "bandwidthGBs": 600},
}
by_rig = {r["key"]: r for r in hardware["rigs"]}
for key, meta in RIGS.items():
    if key in by_rig:
        by_rig[key].update(meta)
    else:
        hardware["rigs"].append({"key": key, **meta, "runCount": 0})
        by_rig[key] = hardware["rigs"][-1]
for rig in hardware["rigs"]:
    ours = [c for c in pool["cells"] if c["rigKey"] == rig["key"] and c.get("hw") and "modal" in str(c.get("hw", ""))]
    if ours:
        rig["runCount"] = sum(c["n"] for c in ours)
hardware["snapshotAt"] = pool["snapshotAt"]

# ---------- stats honestas ----------
text_runs = len(text_rows)
cat_by_slug = {m["slug"]: m.get("category") for m in models["models"]}
stats["cloudAnchors"] = {
    "cells": len(mm_cells), "runs": len(mm_rows) + text_runs,
    "hw": "NVIDIA L4 / A10 24GB (modal.com, 2026-08-31)",
    "categories": sorted({cat_by_slug.get(c["modelSlug"]) or c.get("category") or "chat" for c in mm_cells}),
}
stats["snapshotAt"] = pool["snapshotAt"]

for name, obj in (("pool", pool), ("models", models), ("hardware", hardware), ("stats", stats)):
    json.dump(obj, open(f"{BASE}/{name}.json", "w"), ensure_ascii=False, indent=1)

print(f"ingest anchors ok: +{len(mm_cells)} células "
      f"({len(mm_rows)} runs multimodais + {text_runs} reps texto) — "
      f"categorias: {stats['cloudAnchors']['categories']}")
for c in mm_cells:
    mk = metric_key(c) if c.get("category") else None
    val = c.get(mk) if mk else c.get("tokSOutMedian")
    unit = {"imagesPerSec": "img/s", "audioXReal": "xreal"}.get(mk, "tok/s out")
    print(f"  {c['rigKey']:10s} {c['modelSlug']:42s} n={c['n']} {val} {unit}")
