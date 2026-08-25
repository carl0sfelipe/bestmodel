"""Lab runner: frozen recipe -> warmup + measured runs -> experiments/."""
import datetime
import json
import pathlib
import statistics
import sys
import time

import httpx

from src.analyze_workflow import analyze_file
from src.config import COMFY_BASE_URL, HARDWARE_SNAPSHOT

POLL_INTERVAL_S = 1.0
TIMEOUT_S = 900


def submit(graph):
    response = httpx.post(f"{COMFY_BASE_URL}/prompt", json={"prompt": graph}, timeout=30.0)
    response.raise_for_status()
    return response.json()["prompt_id"]


def wait_done(prompt_id):
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{COMFY_BASE_URL}/history/{prompt_id}", timeout=30.0)
        except httpx.TimeoutException:
            continue  # server busy generating; the outer deadline governs
        response.raise_for_status()
        entry = response.json().get(prompt_id)
        if entry is not None:
            status = entry["status"]
            if status.get("status_str") == "error":
                raise RuntimeError(f"prompt {prompt_id} failed: {status}")
            if status.get("completed"):
                return entry
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"prompt {prompt_id} not done after {TIMEOUT_S}s")


def execution_wall_s(entry):
    # Server-side timestamps (ms) from status messages: excludes queue/poll slack.
    stamps = {name: payload["timestamp"]
              for name, payload in entry["status"]["messages"]
              if name in ("execution_start", "execution_success")}
    return (stamps["execution_success"] - stamps["execution_start"]) / 1000.0


def with_seed(graph, seed):
    seeded = json.loads(json.dumps(graph))
    for node in seeded.values():
        if node["class_type"] == "KSampler":
            node["inputs"]["seed"] = seed
    return seeded


def cached_nodes(entry):
    for name, payload in entry["status"]["messages"]:
        if name == "execution_cached":
            return set(payload.get("nodes", []))
    return set()


def warmup_run(graph):
    # Cache hits are fine here: warmup only ensures the model is resident.
    wait_done(submit(graph))


def timed_run(graph):
    # R-FS detector: sampler served from ComfyUI's execution cache means the
    # wall time measures nothing (SaveImage re-runs even on full cache hits,
    # so file presence is NOT evidence of execution).
    entry = wait_done(submit(graph))
    samplers = {nid for nid, node in graph.items() if node["class_type"] == "KSampler"}
    hit = cached_nodes(entry) & samplers
    if hit:
        raise RuntimeError(
            f"cache hit: sampler nodes {sorted(hit)} served from cache — measurement invalid")
    return execution_wall_s(entry)


def record_experiment(recipe_stem, meta, walls, snapshot, seeds):
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    exp_dir = pathlib.Path("experiments") / f"{timestamp}-{recipe_stem}"
    exp_dir.mkdir(parents=True, exist_ok=False)
    device = snapshot["devices"][0]
    meta_out = {
        "recipe": recipe_stem,
        "recipe_version": meta["recipe_version"],
        "model_file": meta["model_file"],
        "resolution": meta["resolution"],
        "batch_size": meta["batch_size"],
        "steps": meta["steps"],
        "device": {"name": device["name"], "type": device["type"],
                   "vram_total": device["vram_total"]},
        "snapshotCapturedAt": snapshot["capturedAt"],
    }
    wall_stats = {
        "mean": round(statistics.mean(walls), 3),
        "std": round(statistics.stdev(walls), 3) if len(walls) > 1 else 0.0,
        "min": round(min(walls), 3),
        "max": round(max(walls), 3),
        "n": len(walls),
    }
    metrics = {"runs_wall_s": [round(w, 3) for w in walls],
               "seeds": seeds, "wall_s": wall_stats}
    (exp_dir / "meta.json").write_text(json.dumps(meta_out, indent=2) + "\n")
    (exp_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    index_line = {**meta_out, "wall_s": wall_stats, "experiment": exp_dir.name}
    with open(pathlib.Path("experiments") / "index.jsonl", "a") as handle:
        handle.write(json.dumps(index_line) + "\n")
    return exp_dir


def run_recipe(recipe_path):
    recipe_path = pathlib.Path(recipe_path)
    meta = json.loads(recipe_path.with_name(recipe_path.stem + ".meta.json").read_text())
    fit = analyze_file(recipe_path)
    if fit["fit"] == "no":
        print(json.dumps(fit, indent=2), file=sys.stderr)
        sys.exit(4)
    graph = json.loads(recipe_path.read_text())
    for _ in range(meta["warmup_runs"]):
        warmup_run(graph)  # frozen recipe seed as-is
    # Measurement seeds must be unique across sessions against the same
    # server, or the execution cache poisons the timings; recorded in metrics.
    measured_base = int(time.time())
    walls, seeds = [], []
    for i in range(meta["measured_runs"]):
        seed = measured_base + i
        walls.append(timed_run(with_seed(graph, seed)))
        seeds.append(seed)
    snapshot = json.loads(pathlib.Path(HARDWARE_SNAPSHOT).read_text())
    exp_dir = record_experiment(recipe_path.stem, meta, walls, snapshot, seeds)
    print(f"experiment -> {exp_dir} (wall_s mean {statistics.mean(walls):.3f}, n={len(walls)})")
    return exp_dir


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m src.lab_runner <recipes/name.json>", file=sys.stderr)
        sys.exit(1)
    run_recipe(sys.argv[1])
