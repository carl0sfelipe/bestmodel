"""Workflow analyzer: can this machine run this ComfyUI workflow (API format)?"""
import json
import pathlib
import sys

from src.config import HARDWARE_SNAPSHOT, LOCAL_MODELS, PROVISIONAL_TIGHT_FRACTION
from src.report_lab import load_cells

RECOGNIZED_LOADERS = {
    "CheckpointLoaderSimple": ("ckpt_name", ["checkpoints"]),
    "UNETLoader": ("unet_name", ["diffusion_models", "unet"]),
    "VAELoader": ("vae_name", ["vae"]),
}


def parse_workflow(path):
    graph = json.loads(pathlib.Path(path).read_text())
    parsed = {"model_refs": [], "unmapped_loaders": [],
              "resolution": None, "batch_size": None, "steps": None}
    for node in graph.values():
        class_type = node["class_type"]
        inputs = node.get("inputs", {})
        if class_type in RECOGNIZED_LOADERS:
            field, dirs = RECOGNIZED_LOADERS[class_type]
            parsed["model_refs"].append(
                {"file": inputs[field], "dirs": dirs, "loader": class_type})
        elif class_type == "EmptyLatentImage":
            parsed["resolution"] = [inputs["width"], inputs["height"]]
            parsed["batch_size"] = inputs["batch_size"]
        elif class_type == "KSampler":
            parsed["steps"] = inputs["steps"]
        elif any(key.endswith("_name") for key in inputs):
            parsed["unmapped_loaders"].append(class_type)
    return parsed


def resolve_models(parsed, catalog):
    models = catalog["models"]
    by_file = {}
    for entry in models:
        by_file.setdefault(entry["file"], []).append(entry)
    resolved, missing = [], []
    for ref in parsed["model_refs"]:
        matches = [e for e in by_file.get(ref["file"], []) if e["dir"] in ref["dirs"]]
        if matches:
            resolved.append(matches[0])
        else:
            missing.append(ref["file"])
    return {"resolved": resolved, "missing_files": missing}


def match_cell(cells, resolved, parsed):
    files = {e["file"] for e in resolved["resolved"]}
    for cell in cells:
        if (cell["model_file"] in files
                and cell["s_per_image"]["n"] >= 3  # n < 3 never counts as measured
                and cell["resolution"] == parsed["resolution"]
                and cell["batch_size"] == parsed["batch_size"]
                and cell["steps"] == parsed["steps"]):
            return cell
    return None


def verdict(parsed, resolved, snapshot, cells=()):
    vram_total = snapshot["devices"][0]["vram_total"]
    weights_bytes = sum(e["bytes"] for e in resolved["resolved"])
    reasons = []
    if resolved["missing_files"]:
        fit = "no"
        reasons = [f"model file not found: {name}" for name in resolved["missing_files"]]
    elif weights_bytes > vram_total:
        fit = "no"
        reasons.append("weights exceed vram_total")
    elif weights_bytes > PROVISIONAL_TIGHT_FRACTION * vram_total:
        fit = "tight"
    else:
        fit = "ok"
    basis, estimate = "extrapolated", None
    if fit != "no":
        cell = match_cell(cells, resolved, parsed)
        if cell:
            basis = "measured"
            estimate = cell["s_per_image"]["mean"]
    return {
        "fit": fit,
        "basis": basis,
        "weights_bytes": weights_bytes,
        "vram_total": vram_total,
        "resolution": parsed["resolution"],
        "batch_size": parsed["batch_size"],
        "steps": parsed["steps"],
        "estimate_s_per_image": estimate,
        "unmapped_loaders": parsed["unmapped_loaders"],
        "missing_files": resolved["missing_files"],
        "reasons": reasons,
    }


def analyze_file(workflow_path):
    snapshot_path = pathlib.Path(HARDWARE_SNAPSHOT)
    if not snapshot_path.is_file():
        print(f"hardware snapshot not found at {snapshot_path}; "
              "run `python -m src.probe_hardware` with the server up (S4)", file=sys.stderr)
        sys.exit(3)
    catalog = json.loads(pathlib.Path(LOCAL_MODELS).read_text())
    snapshot = json.loads(snapshot_path.read_text())
    parsed = parse_workflow(workflow_path)
    resolved = resolve_models(parsed, catalog)
    return verdict(parsed, resolved, snapshot, load_cells())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m src.analyze_workflow <workflow.json>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(analyze_file(sys.argv[1]), indent=2))
