"""Aggregate lab experiments into measured cells; measured-vs-estimated report."""
import datetime
import json
import pathlib
import statistics
import sys


def load_cells(experiments_dir="experiments"):
    root = pathlib.Path(experiments_dir)
    index_path = root / "index.jsonl"
    if not index_path.is_file():
        return []
    groups = {}
    for line in index_path.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        key = (entry["model_file"], tuple(entry["resolution"]),
               entry["batch_size"], entry["steps"], entry["recipe_version"])
        metrics = json.loads((root / entry["experiment"] / "metrics.json").read_text())
        group = groups.setdefault(key, {
            "recipe": entry["recipe"],
            "recipe_version": entry["recipe_version"],
            "model_file": entry["model_file"],
            "resolution": entry["resolution"],
            "batch_size": entry["batch_size"],
            "steps": entry["steps"],
            "runs": [],
            "peaks": [],
        })
        group["runs"].extend(metrics["runs_wall_s"])
        if "peak_bytes" in metrics:  # written by the S5 instrumentation node
            group["peaks"].append(metrics["peak_bytes"])
    cells = []
    for group in groups.values():
        runs = group.pop("runs")
        peaks = group.pop("peaks")
        group["s_per_image"] = {
            "mean": round(statistics.mean(runs), 3),
            "std": round(statistics.stdev(runs), 3) if len(runs) > 1 else 0.0,
            "n": len(runs),
        }
        group["peak_bytes"] = max(peaks) if peaks else None
        cells.append(group)
    return cells


def report_json(cells):
    return {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cells": cells,
    }


def report_markdown(cells):
    lines = ["| recipe | modelo | s/img mean±std | peak VRAM | n |",
             "|---|---|---|---|---|"]
    for cell in cells:
        s = cell["s_per_image"]
        peak = f"{cell['peak_bytes'] / 1e9:.2f}GB" if cell["peak_bytes"] else "—"
        lines.append(f"| {cell['recipe']} ({cell['recipe_version']}) | {cell['model_file']} "
                     f"| {s['mean']}±{s['std']}s | {peak} | {s['n']} |")
    return "\n".join(lines)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) == 2 else "--markdown"
    if mode not in ("--json", "--markdown"):
        print("usage: python -m src.report_lab [--json|--markdown]", file=sys.stderr)
        sys.exit(1)
    loaded = load_cells()
    if mode == "--json":
        print(json.dumps(report_json(loaded), indent=2))
    else:
        print(report_markdown(loaded))
