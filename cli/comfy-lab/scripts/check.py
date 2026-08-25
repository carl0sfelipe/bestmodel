#!/usr/bin/env python3
"""Single oracle for the bestmodel-comfy pack: check.py <target> (exit 2 reserved)."""
import json
import pathlib
import sys

PACK_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACK_ROOT))


def check_scaffold():
    from src import config
    assert config.COMFY_BASE_URL == "http://127.0.0.1:8188", config.COMFY_BASE_URL
    assert config.RECIPE_VERSION == "comfy-r1", config.RECIPE_VERSION
    assert config.PROVISIONAL_TIGHT_FRACTION == 0.8, config.PROVISIONAL_TIGHT_FRACTION
    fixture_path = PACK_ROOT / "tests/fixtures/system-stats-synthetic.json"
    fixture = json.loads(fixture_path.read_text())
    vram_total = fixture["devices"][0]["vram_total"]
    assert isinstance(vram_total, int) and vram_total > 0, vram_total
    assert fixture["source"] == "synthetic", fixture.get("source")
    print("scaffold: ok")


def check_models():
    from src import config
    from src.scan_models import scan
    fixture_root = PACK_ROOT / "tests/fixtures/models-tree"
    entries = scan(fixture_root)
    assert len(entries) == 3, entries
    expected = {
        "dummy-sd15.safetensors": ("checkpoints", "safetensors"),
        "dummy-xl.ckpt": ("checkpoints", "ckpt"),
        "dummy-vae.pt": ("vae", "pt"),
    }
    by_name = {e["file"]: e for e in entries}
    for name, (subdir, fmt) in expected.items():
        entry = by_name[name]
        assert entry["dir"] == subdir and entry["format"] == fmt, entry
        real_bytes = (fixture_root / "models" / subdir / name).stat().st_size
        assert entry["bytes"] == real_bytes and entry["bytes"] > 0, entry
    real_models = pathlib.Path(config.COMFY_ROOT) / "models"
    for subdir in config.MODEL_DIRS:
        assert (real_models / subdir).is_dir(), f"missing model dir: {real_models / subdir}"
    real_entries = scan(config.COMFY_ROOT)
    assert isinstance(real_entries, list), type(real_entries)
    print(f"models: ok (fixture 3, real {len(real_entries)})")


def check_analyze():
    from src.analyze_workflow import parse_workflow, resolve_models, verdict
    from src.scan_models import scan
    fixtures = PACK_ROOT / "tests/fixtures"
    catalog = {"models": scan(fixtures / "models-tree")}
    snapshot = json.loads((fixtures / "system-stats-synthetic.json").read_text())
    parsed = parse_workflow(fixtures / "workflow-basic.json")
    result = verdict(parsed, resolve_models(parsed, catalog), snapshot)
    assert result["fit"] == "ok", result
    assert result["estimate_s_per_image"] is None, result
    assert result["basis"] == "extrapolated", result
    assert result["missing_files"] == [] and result["unmapped_loaders"] == [], result
    assert result["resolution"] == [1024, 1024] and result["steps"] == 4, result
    parsed_unmapped = parse_workflow(fixtures / "workflow-unmapped.json")
    assert parsed_unmapped["unmapped_loaders"] == ["FakeLoaderXYZ"], parsed_unmapped
    ghost = {"model_refs": [{"file": "ghost.safetensors", "dirs": ["checkpoints"],
                             "loader": "CheckpointLoaderSimple"}],
             "unmapped_loaders": [], "resolution": None, "batch_size": None, "steps": None}
    ghost_verdict = verdict(ghost, resolve_models(ghost, catalog), snapshot)
    assert ghost_verdict["fit"] == "no", ghost_verdict
    assert ghost_verdict["reasons"] == ["model file not found: ghost.safetensors"], ghost_verdict
    print("analyze: ok")


def server_up():
    import httpx
    from src.config import COMFY_BASE_URL
    try:
        httpx.get(f"{COMFY_BASE_URL}/system_stats", timeout=2.0)
        return True
    except httpx.ConnectError:
        return False


def check_lab():
    if not server_up():
        print("lab: server down; run scripts/comfy-server.sh start", file=sys.stderr)
        sys.exit(1)
    from src.config import HARDWARE_SNAPSHOT
    from src.lab_runner import run_recipe
    from src.probe_hardware import fetch_system_stats, snapshot_to_file
    snapshot_to_file(fetch_system_stats(), PACK_ROOT / HARDWARE_SNAPSHOT)
    snapshot = json.loads((PACK_ROOT / HARDWARE_SNAPSHOT).read_text())
    assert snapshot["source"] == "live", snapshot.get("source")
    index_path = PACK_ROOT / "experiments/index.jsonl"
    lines_before = len(index_path.read_text().splitlines()) if index_path.is_file() else 0
    exp_dir = run_recipe(PACK_ROOT / "recipes/sd15-512.json")
    lines_after = len(index_path.read_text().splitlines())
    assert lines_after == lines_before + 1, (lines_before, lines_after)
    metrics = json.loads((exp_dir / "metrics.json").read_text())
    assert len(metrics["runs_wall_s"]) == 3, metrics
    assert metrics["wall_s"]["n"] == 3, metrics
    assert all(w > 0 for w in metrics["runs_wall_s"]), metrics
    assert len(set(metrics["seeds"])) == 3, metrics  # R-FS: distinct seeds per measured run
    print(f"lab: ok (wall_s mean {metrics['wall_s']['mean']}s, n=3, warmup excluded)")


def check_report():
    from src.analyze_workflow import analyze_file
    from src.report_lab import load_cells, report_markdown
    cells = load_cells(PACK_ROOT / "experiments")
    measured = [c for c in cells if c["s_per_image"]["n"] >= 3]
    assert measured, "no measured cell with n >= 3 (run check.py lab first)"
    markdown = report_markdown(cells)
    assert "comfy-r1" in markdown, markdown
    result = analyze_file(PACK_ROOT / "recipes/sd15-512.json")
    assert result["basis"] == "measured", result
    assert result["estimate_s_per_image"] is not None, result
    print(f"report: ok ({len(measured)} measured cells; frozen recipe "
          f"estimate {result['estimate_s_per_image']}s/img)")


def check_bestfit():
    import subprocess
    from src.best_fit import rank_models
    from src.report_lab import load_cells
    fixtures = PACK_ROOT / "tests/fixtures"
    catalog = json.loads((fixtures / "catalog-synthetic.json").read_text())
    snapshot = json.loads((fixtures / "system-stats-synthetic.json").read_text())
    cells = load_cells(fixtures / "experiments-synthetic")
    ranking = rank_models(catalog, snapshot, cells)
    names = [e["model"] for e in ranking]
    assert names == ["ok-2g.safetensors", "small-1g.safetensors",
                     "tight-7g.safetensors", "big-9g.safetensors"], names
    assert [e["fit"] for e in ranking] == ["ok", "ok", "tight", "no"], ranking
    by_name = {e["model"]: e for e in ranking}
    assert by_name["ok-2g.safetensors"]["s_per_image"] == \
        {"value": 12.367, "basis": "measured", "n": 3}, by_name["ok-2g.safetensors"]
    assert by_name["small-1g.safetensors"]["s_per_image"] == \
        {"value": None, "basis": None, "n": 0}, by_name["small-1g.safetensors"]  # n=2 < 3
    assert "aux-vae.pt" not in by_name, names
    run_json = subprocess.run([sys.executable, "-m", "src.best_fit", "--json"],
                              capture_output=True, text=True, cwd=PACK_ROOT)
    assert run_json.returncode == 0, run_json.stderr
    payload = json.loads(run_json.stdout)
    assert payload["ranking"] and payload["quality_proxy"] == "largest-that-fits-v1", payload
    run_md = subprocess.run([sys.executable, "-m", "src.best_fit", "--markdown"],
                            capture_output=True, text=True, cwd=PACK_ROOT)
    assert run_md.returncode == 0, run_md.stderr
    assert "melhor que cabe:" in run_md.stdout, run_md.stdout
    best = payload["best"]["model"] if payload["best"] else "nenhum"
    print(f"bestfit: ok (fixture: 4 ranqueados, aux excluído; real: best = {best})")


SERVER_TARGETS = {"lab"}
TARGETS = {"scaffold": check_scaffold, "models": check_models,
           "analyze": check_analyze, "lab": check_lab, "report": check_report,
           "bestfit": check_bestfit}


def main():
    known = ", ".join([*TARGETS, "all"])
    if len(sys.argv) != 2:
        print(f"usage: check.py <target>; targets: {known}", file=sys.stderr)
        sys.exit(1)
    target = sys.argv[1]
    if target == "all":
        for name, fn in TARGETS.items():
            if name in SERVER_TARGETS and not server_up():
                print(f"{name}: SKIPPED (server down)", file=sys.stderr)
                continue
            fn()
        return
    if target not in TARGETS:
        print(f"unknown target {target!r}; targets: {known}", file=sys.stderr)
        sys.exit(1)
    TARGETS[target]()


if __name__ == "__main__":
    main()
