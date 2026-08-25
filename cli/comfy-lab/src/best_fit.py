"""Best fit: which local image model fits this hardware, and how fast per image?"""
import datetime
import json
import pathlib
import sys

from src.config import HARDWARE_SNAPSHOT, LOCAL_MODELS, PROVISIONAL_TIGHT_FRACTION
from src.report_lab import load_cells

MAIN_DIRS = {"checkpoints", "diffusion_models", "unet"}  # vae/clip/loras are auxiliary
QUALITY_PROXY = "largest-that-fits-v1"
FIT_ORDER = {"ok": 0, "tight": 1, "no": 2}


def model_fit(weight_bytes, vram_total):
    if weight_bytes > vram_total:
        return "no"
    if weight_bytes > PROVISIONAL_TIGHT_FRACTION * vram_total:
        return "tight"
    return "ok"


def cell_for(cells, model_file):
    candidates = [c for c in cells
                  if c["model_file"] == model_file and c["s_per_image"]["n"] >= 3]
    if not candidates:
        return None
    return max(candidates, key=lambda c: c["s_per_image"]["n"])


def rank_models(catalog, snapshot, cells):
    vram_total = snapshot["devices"][0]["vram_total"]
    ranking = []
    for model in catalog["models"]:
        if model["dir"] not in MAIN_DIRS:
            continue
        cell = cell_for(cells, model["file"])
        s_per_image = ({"value": cell["s_per_image"]["mean"], "basis": "measured",
                        "n": cell["s_per_image"]["n"]}
                       if cell else {"value": None, "basis": None, "n": 0})
        ranking.append({
            "model": model["file"],
            "dir": model["dir"],
            "bytes": model["bytes"],
            "fit": model_fit(model["bytes"], vram_total),
            "s_per_image": s_per_image,
        })
    ranking.sort(key=lambda e: (FIT_ORDER[e["fit"]], -e["bytes"], e["model"]))
    return ranking


def to_markdown(ranking):
    lines = ["| # | modelo | fit | s/img (basis, n) | GB |", "|---|---|---|---|---|"]
    for pos, entry in enumerate(ranking, 1):
        s = entry["s_per_image"]
        s_col = f"{s['value']} ({s['basis']}, n={s['n']})" if s["value"] is not None else "null"
        lines.append(f"| {pos} | {entry['model']} | {entry['fit']} | {s_col} "
                     f"| {entry['bytes'] / 1e9:.1f} |")
    best = next((e for e in ranking if e["fit"] != "no"), None)
    lines.append(f"melhor que cabe: {best['model'] if best else 'nenhum'}")
    return "\n".join(lines)


def to_json(ranking, snapshot):
    device = snapshot["devices"][0]
    best = next((e for e in ranking if e["fit"] != "no"), None)
    return {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hardware": {"name": device["name"], "type": device["type"],
                     "vram_total": device["vram_total"]},
        "quality_proxy": QUALITY_PROXY,
        "ranking": ranking,
        "best": best,
    }


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) == 2 else "--markdown"
    if mode not in ("--json", "--markdown"):
        print("usage: python -m src.best_fit [--json|--markdown]", file=sys.stderr)
        sys.exit(1)
    snapshot_path = pathlib.Path(HARDWARE_SNAPSHOT)
    if not snapshot_path.is_file():
        print(f"hardware snapshot not found at {snapshot_path}; "
              "run `python -m src.probe_hardware` with the server up", file=sys.stderr)
        sys.exit(3)
    catalog = json.loads(pathlib.Path(LOCAL_MODELS).read_text())
    snapshot = json.loads(snapshot_path.read_text())
    ranked = rank_models(catalog, snapshot, load_cells())
    if mode == "--json":
        print(json.dumps(to_json(ranked, snapshot), indent=2))
    else:
        print(to_markdown(ranked))
