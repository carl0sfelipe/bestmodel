#!/usr/bin/env python
"""Single oracle for bestmodel-backend sessions.

Usage: uv run python scripts/check.py <target>
Targets: scaffold, sync, flags, derived, match, ops, all.
Exit codes: 0 ok, 1 target failed or unknown (2 is reserved, never used).
"""

import sys
from typing import Callable

TARGETS: dict[str, Callable[[], None]] = {}


def target(name: str) -> Callable[[Callable[[], None]], Callable[[], None]]:
    def register(fn: Callable[[], None]) -> Callable[[], None]:
        TARGETS[name] = fn
        return fn

    return register


def _import_config() -> None:
    import src.config

    if src.config.API_PORT != 8790:
        raise AssertionError(f"API_PORT={src.config.API_PORT}, expected 8790")
    if src.config.SUSPICIOUS_FRACTION != 0.92:
        raise AssertionError(
            f"SUSPICIOUS_FRACTION={src.config.SUSPICIOUS_FRACTION}, expected 0.92"
        )
    if src.config.THROTTLE_MS != 350:
        raise AssertionError(f"THROTTLE_MS={src.config.THROTTLE_MS}, expected 350")


@target("scaffold")
def check_scaffold() -> None:
    _import_config()

    from fastapi.testclient import TestClient

    from src.main import app

    response = TestClient(app).get("/healthz")
    if response.status_code != 200:
        raise AssertionError(f"/healthz status={response.status_code}, expected 200")
    body = response.json()
    if body.get("ok") is not True:
        raise AssertionError(f"/healthz body={body!r}, ok != true")
    for key in ("runs", "lastSyncAt"):
        if key not in body:
            raise AssertionError(f"/healthz missing key {key!r}")


@target("sync")
def check_sync() -> None:
    _import_config()

    import os

    import src.db
    from src.sync_pool import BANDWIDTH_SEED_GBS

    db_path = src.config.DB_PATH
    if not os.path.exists(db_path):
        raise AssertionError(f"database not found: {db_path} (run src.sync_pool first)")

    conn = src.db.connect()

    run_count = conn.execute("SELECT COUNT(*) FROM lm_run").fetchone()[0]
    if run_count < 4500:
        raise AssertionError(f"COUNT(lm_run)={run_count}, expected >= 4500")

    model_count = conn.execute("SELECT COUNT(*) FROM lm_model").fetchone()[0]
    if model_count < 400:
        raise AssertionError(f"COUNT(lm_model)={model_count}, expected >= 400")

    unresolved = conn.execute(
        """SELECT COUNT(*) FROM lm_run r
           LEFT JOIN lm_model m ON m.slug = r.model_slug
           LEFT JOIN lm_rig rg ON rg.key = r.rig_key
           WHERE m.slug IS NULL OR rg.key IS NULL"""
    ).fetchone()[0]
    if unresolved:
        raise AssertionError(f"{unresolved} lm_run rows with unresolved FKs")

    meta = {
        row["key"]: row["value"]
        for row in conn.execute("SELECT key, value FROM sync_meta")
    }
    for key in ("last_sync_at", "remote_total", "synced_runs"):
        if key not in meta:
            raise AssertionError(f"sync_meta missing key {key!r}")

    allowed = set(BANDWIDTH_SEED_GBS.values())
    banned = [
        row["bandwidth_gbs"]
        for row in conn.execute(
            "SELECT DISTINCT bandwidth_gbs FROM lm_rig WHERE bandwidth_gbs IS NOT NULL"
        )
        if row["bandwidth_gbs"] not in allowed
    ]
    if banned:
        raise AssertionError(f"bandwidth_gbs outside seed set: {banned}")

    synced = int(meta["synced_runs"])
    if synced != run_count:
        raise AssertionError(
            f"COUNT(lm_run)={run_count} != synced_runs={synced} (idempotency)"
        )

    conn.close()


def _summary_via_sql(conn) -> dict:
    """Independent summary recomputation straight from SQL (zero tolerance)."""
    total = conn.execute("SELECT COUNT(*) FROM lm_run").fetchone()[0]
    counts = {v: 0 for v in ("ok", "suspicious", "impossible", "exempt")}
    for row in conn.execute(
        "SELECT verdict, COUNT(*) AS n FROM plausibility_flag GROUP BY verdict"
    ):
        counts[row["verdict"]] = row["n"]
    worst = [
        {
            "runId": row["run_id"],
            "modelSlug": row["model_slug"],
            "rigKey": row["rig_key"],
            "ratio": row["ratio"],
        }
        for row in conn.execute(
            """SELECT p.run_id, r.model_slug, r.rig_key, p.ratio
               FROM plausibility_flag p
               JOIN lm_run r ON r.id = p.run_id
               WHERE p.verdict IN ('impossible','suspicious')
               ORDER BY p.ratio DESC
               LIMIT 10"""
        )
    ]
    return {
        "total": total,
        "ok": counts["ok"],
        "suspicious": counts["suspicious"],
        "impossible": counts["impossible"],
        "exempt": counts["exempt"],
        "worst": worst,
    }


@target("flags")
def check_flags() -> None:
    _import_config()

    import os

    import src.db
    from src.plausibility import REASON_MISSING_INPUTS

    db_path = src.config.DB_PATH
    if not os.path.exists(db_path):
        raise AssertionError(f"database not found: {db_path} (run src.sync_pool first)")

    conn = src.db.connect()

    run_count = conn.execute("SELECT COUNT(*) FROM lm_run").fetchone()[0]
    flag_count = conn.execute("SELECT COUNT(*) FROM plausibility_flag").fetchone()[0]
    if flag_count != run_count:
        raise AssertionError(
            f"COUNT(plausibility_flag)={flag_count} != COUNT(lm_run)={run_count}"
        )

    allowed = {"ok", "suspicious", "impossible", "exempt"}
    verdicts = {
        row["verdict"]
        for row in conn.execute("SELECT DISTINCT verdict FROM plausibility_flag")
    }
    if not verdicts <= allowed:
        raise AssertionError(f"verdicts outside {allowed}: {verdicts - allowed}")

    exempt_ratio = conn.execute(
        """SELECT COUNT(*) FROM plausibility_flag
           WHERE verdict = 'exempt' AND ratio != 0.0"""
    ).fetchone()[0]
    if exempt_ratio:
        raise AssertionError(
            f"{exempt_ratio} exempt runs have a computed ratio (expected 0.0 sentinel)"
        )

    bad_missing = conn.execute(
        """SELECT COUNT(*) FROM plausibility_flag p
           JOIN lm_run r ON r.id = p.run_id
           JOIN lm_model m ON m.slug = r.model_slug
           JOIN lm_rig rg ON rg.key = r.rig_key
           WHERE p.reason = ? AND p.verdict = 'exempt'
             AND rg.bandwidth_gbs IS NOT NULL
             AND r.bits IS NOT NULL
             AND COALESCE(
                 CASE WHEN m.is_moe THEN m.active_params_b ELSE m.params_b END, 0
             ) > 0""",
        (REASON_MISSING_INPUTS,),
    ).fetchone()[0]
    if bad_missing:
        raise AssertionError(
            f"{bad_missing} missing_inputs exempt runs have all inputs present"
        )

    from fastapi.testclient import TestClient

    from src.main import app

    endpoint = TestClient(app).get("/v1/plausibility/summary").json()
    direct = _summary_via_sql(conn)
    if endpoint != direct:
        raise AssertionError(f"summary mismatch:\nendpoint={endpoint}\nSQL={direct}")

    conn.close()


RIG_KEYS = ["key", "label", "hwClass", "memGb", "gpuCount", "bandwidthGBs", "runCount"]
MODEL_KEYS = [
    "slug", "hfId", "displayName", "family", "paramsB", "activeParamsB", "isMoE",
    "category", "runCount", "medianTokS", "evalScore", "vramMeasuredGb",
    "maxContextTested",
]
CELL_KEYS = [
    "rigKey", "modelSlug", "bits", "n", "tokSOutMedian", "tokSPrefillMedian",
    "ttftMsMedian", "peakVramGbMedian", "maxContextTested", "engines",
]


def _require_keys(obj: dict, keys: list[str], where: str) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        raise AssertionError(f"{where}: missing keys {missing}")


@target("derived")
def check_derived() -> None:
    _import_config()

    import json
    import os
    import re

    import src.db
    from src.derive_export import OUT_DIR, PUBLISH_MARKER, WEB_DERIVED_DIR

    parsed: dict[str, dict] = {}
    for name in ("hardware", "models", "pool", "stats"):
        path = os.path.join(OUT_DIR, f"{name}.json")
        if not os.path.exists(path):
            raise AssertionError(f"missing {path} (run src.derive_export first)")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        if re.search(r"\bNaN\b|\bInfinity\b", text):
            raise AssertionError(f"{path} contains NaN/Infinity")
        parsed[name] = json.loads(text)

    rigs = parsed["hardware"]["rigs"]
    models = parsed["models"]["models"]
    cells = parsed["pool"]["cells"]
    stats = parsed["stats"]
    if not rigs or not models or not cells:
        raise AssertionError(f"empty array: rigs={len(rigs)} models={len(models)} cells={len(cells)}")

    _require_keys(rigs[0], RIG_KEYS, "hardware.rigs[0]")
    _require_keys(models[0], MODEL_KEYS, "models.models[0]")
    _require_keys(cells[0], CELL_KEYS, "pool.cells[0]")
    _require_keys(stats, ["snapshotAt", "totals", "topRigs", "topModels", "curation"], "stats")
    _require_keys(stats["curation"], ["excludedImpossible", "flaggedSuspicious", "computedAt"], "stats.curation")

    if len(cells) < 500:
        raise AssertionError(f"cells {len(cells)} < 500")

    rig_keys = {rig["key"] for rig in rigs}
    model_slugs = {model["slug"] for model in models}
    for cell in cells:
        if cell["rigKey"] not in rig_keys:
            raise AssertionError(f"cell points to unknown rig {cell['rigKey']}")
        if cell["modelSlug"] not in model_slugs:
            raise AssertionError(f"cell points to unknown model {cell['modelSlug']}")

    db_path = src.config.DB_PATH
    if not os.path.exists(db_path):
        raise AssertionError(f"database not found: {db_path}")
    conn = src.db.connect()
    try:
        last_sync_at = conn.execute(
            "SELECT value FROM sync_meta WHERE key = 'last_sync_at'"
        ).fetchone()[0]
        for name in ("hardware", "models", "pool", "stats"):
            if parsed[name].get("snapshotAt") != last_sync_at:
                raise AssertionError(f"{name}.json snapshotAt != last_sync_at")

        excluded = conn.execute(
            """SELECT COUNT(*) FROM lm_run r
               JOIN plausibility_flag p ON p.run_id = r.id
               WHERE p.verdict = 'impossible' AND r.bits IS NOT NULL"""
        ).fetchone()[0]
        if stats["curation"]["excludedImpossible"] != excluded:
            raise AssertionError(
                f"curation.excludedImpossible={stats['curation']['excludedImpossible']} "
                f"!= SQL count {excluded}"
            )
    finally:
        conn.close()

    marker = os.path.join(OUT_DIR, PUBLISH_MARKER)
    if os.path.exists(marker):
        for name in ("hardware", "models", "pool", "stats"):
            web_path = os.path.join(WEB_DERIVED_DIR, f"{name}.json")
            if not os.path.exists(web_path):
                raise AssertionError(f"published file missing: {web_path}")
            with open(os.path.join(OUT_DIR, f"{name}.json"), "rb") as local, open(web_path, "rb") as remote:
                if local.read() != remote.read():
                    raise AssertionError(f"{web_path} differs from {OUT_DIR}/{name}.json")


RIG_3090 = {
    "key": "rtx-3090-24gb", "label": "RTX 3090 24GB", "hwClass": "DISCRETE_GPU",
    "memGb": 24.0, "gpuCount": 1, "bandwidthGBs": 936.2, "runCount": 1,
}
RIG_MAC = {
    "key": "m3-ultra-512gb", "label": "M3 Ultra 512GB", "hwClass": "UNIFIED",
    "memGb": 512.0, "gpuCount": 1, "bandwidthGBs": 800.0, "runCount": 1,
}
RIG_NO_BW = {
    "key": "mystery-16gb", "label": "Mystery 16GB", "hwClass": "DISCRETE_GPU",
    "memGb": 16.0, "gpuCount": 1, "bandwidthGBs": None, "runCount": 1,
}
MODEL_7B = {"slug": "qwen-7b", "paramsB": 7.0, "isMoE": False, "vramMeasuredGb": {}}
MODEL_MEASURED = {
    "slug": "llama-13b", "paramsB": 13.0, "isMoE": False,
    "vramMeasuredGb": {"4": {"gb": 19.0, "n": 5}},
}
FIXTURE_CELLS = [
    {"rigKey": "rtx-3090-24gb", "modelSlug": "qwen-7b", "bits": 4, "n": 5, "tokSOutMedian": 60.0},
    {"rigKey": "rtx-3090-24gb", "modelSlug": "llama-13b", "bits": 4, "n": 1, "tokSOutMedian": 34.0},
    {"rigKey": "m3-ultra-512gb", "modelSlug": "qwen-7b", "bits": 8, "n": 4, "tokSOutMedian": 40.0},
]
FIXTURE_RIGS = [RIG_3090, RIG_MAC, RIG_NO_BW]


def _check_engine_rules() -> None:
    """Pure-engine checks mirroring the web S3 spec (fit/estimate/topPicks)."""
    from src.derive_export import round2
    from src.match import (
        estimate_tok_s, fit_class, top_picks, usable_mem_gb, vram_needed_gb,
    )

    if usable_mem_gb(RIG_3090) != 24.0 * 0.90:
        raise AssertionError("usableMemGb discrete fraction wrong")
    if usable_mem_gb(RIG_MAC) != 512.0 * 0.75:
        raise AssertionError("usableMemGb unified fraction wrong")
    if usable_mem_gb({**RIG_3090, "memGb": None}) is not None:
        raise AssertionError("usableMemGb with null memGb should be null")

    need = vram_needed_gb(MODEL_MEASURED, 4)
    if need != {"gb": 19.0, "basis": "measured"}:
        raise AssertionError(f"vramNeeded measured path: {need!r}")
    formula = vram_needed_gb(MODEL_7B, 4)
    if formula["basis"] != "formula" or formula["gb"] != 0.15 * 4 * 7 + 2.0:
        raise AssertionError(f"vramNeeded formula path: {formula!r}")

    order = {"no": 0, "tight": 1, "ok": 2, "head": 3}
    prev = float("inf")
    for bits in (1, 2, 3, 4, 5, 6, 8, 16):
        fit = fit_class(RIG_3090, MODEL_7B, bits)
        if order[fit] > prev:
            raise AssertionError(f"fitClass not monotonic in bits={bits}")
        prev = order[fit]

    measured = estimate_tok_s(RIG_3090, MODEL_7B, 4, FIXTURE_CELLS, FIXTURE_RIGS)
    if measured != {"value": 60.0, "basis": "measured", "n": 5}:
        raise AssertionError(f"estimate measured path: {measured!r}")
    reported = estimate_tok_s(RIG_3090, MODEL_MEASURED, 4, FIXTURE_CELLS, FIXTURE_RIGS)
    if reported["basis"] != "reported" or reported["n"] != 1:
        raise AssertionError(f"estimate reported path: {reported!r}")
    extrapolated = estimate_tok_s(RIG_3090, MODEL_7B, 8, FIXTURE_CELLS, FIXTURE_RIGS)
    expected = round2(40.0 * (936.2 / 800.0))
    if extrapolated != {"value": expected, "basis": "extrapolated", "n": 4}:
        raise AssertionError(f"estimate extrapolated path: {extrapolated!r}")
    if estimate_tok_s(RIG_NO_BW, MODEL_7B, 8, FIXTURE_CELLS, FIXTURE_RIGS) is not None:
        raise AssertionError("estimate without bandwidth must be null")

    picks = top_picks(RIG_3090, [MODEL_7B, MODEL_MEASURED], FIXTURE_CELLS, FIXTURE_RIGS, 10)
    if not picks:
        raise AssertionError("topPicks returned no picks on fixture")
    if picks[0]["est"]["basis"] != "measured" or picks[0]["model"]["slug"] != "qwen-7b":
        raise AssertionError(f"topPicks head must be measured qwen-7b: {picks[0]!r}")
    for pick in picks:
        if pick["fit"] not in ("ok", "head"):
            raise AssertionError(f"topPicks returned non ok/head fit {pick['fit']!r}")
    weights = {"measured": 3, "reported": 2, "extrapolated": 1}
    for index in range(1, len(picks)):
        if weights[picks[index - 1]["est"]["basis"]] < weights[picks[index]["est"]["basis"]]:
            raise AssertionError("topPicks ranking violated basis weight order")


@target("match")
def check_match() -> None:
    _import_config()
    _check_engine_rules()

    import os

    import src.db
    import src.derive_export
    from fastapi.testclient import TestClient

    from src.main import app

    db_path = src.config.DB_PATH
    if not os.path.exists(db_path):
        raise AssertionError(f"database not found: {db_path} (run src.sync_pool first)")
    conn = src.db.connect()
    client = TestClient(app)
    try:
        total_runs = conn.execute("SELECT COUNT(*) FROM lm_run").fetchone()[0]
        last_sync = conn.execute(
            "SELECT value FROM sync_meta WHERE key = 'last_sync_at'"
        ).fetchone()[0]

        hz = client.get("/healthz").json()
        if hz.get("ok") is not True:
            raise AssertionError(f"healthz ok != true: {hz!r}")
        if hz.get("runs") != total_runs:
            raise AssertionError(f"healthz runs={hz.get('runs')} != SQL {total_runs}")
        if hz.get("lastSyncAt") != last_sync:
            raise AssertionError(f"healthz lastSyncAt={hz.get('lastSyncAt')!r} != {last_sync!r}")

        top_rig = conn.execute(
            "SELECT key FROM lm_rig ORDER BY run_count DESC LIMIT 1"
        ).fetchone()[0]
        response = client.get(f"/v1/match/hardware-to-models?rig_key={top_rig}&bits=4&k=10")
        if response.status_code != 200:
            raise AssertionError(f"hardware-to-models status={response.status_code}")
        body = response.json()
        if body.get("rig", {}).get("key") != top_rig:
            raise AssertionError("hardware-to-models returned wrong rig")
        picks = body.get("picks", [])
        if not any(
            pick.get("estimate", {}).get("basis") == "measured" for pick in picks
        ):
            raise AssertionError(
                f"no measured pick for top rig {top_rig} (identity bug S2/S4/S5)"
            )
        allowed_basis = {"measured", "reported", "extrapolated"}
        for pick in picks:
            basis = pick.get("estimate", {}).get("basis")
            if basis not in allowed_basis:
                raise AssertionError(f"pick basis {basis!r} outside {allowed_basis}")
            if pick.get("fit") not in ("ok", "head"):
                raise AssertionError(f"pick fit {pick.get('fit')!r} not ok/head")

        top_model = conn.execute(
            """SELECT m.slug FROM lm_model m
               JOIN lm_run r ON r.model_slug = m.slug
               JOIN plausibility_flag p ON p.run_id = r.id
               WHERE p.verdict != 'impossible'
               GROUP BY m.slug ORDER BY COUNT(r.id) DESC, m.slug LIMIT 1"""
        ).fetchone()[0]
        biggest_cell_rig = conn.execute(
            """SELECT r.rig_key FROM lm_run r
               JOIN plausibility_flag p ON p.run_id = r.id
               WHERE r.model_slug = ? AND r.bits = 4 AND p.verdict != 'impossible'
                 AND COALESCE(r.batch_size, 1) <= 1 AND COALESCE(r.concurrency, 1) <= 1
               GROUP BY r.rig_key ORDER BY COUNT(r.id) DESC, r.rig_key LIMIT 1""",
            (top_model,),
        ).fetchone()[0]
        reverse = client.get(
            f"/v1/match/model-to-hardware?model_slug={top_model}&bits=4&k=500"
        )
        if reverse.status_code != 200:
            raise AssertionError(f"model-to-hardware status={reverse.status_code}")
        entries = reverse.json().get("rigs", [])
        rig_keys = [entry["rig"]["key"] for entry in entries]
        if biggest_cell_rig not in rig_keys:
            raise AssertionError(
                f"model-to-hardware for {top_model} misses its biggest-cell rig "
                f"{biggest_cell_rig}"
            )

        cells = {
            (cell["rigKey"], cell["modelSlug"], cell["bits"])
            for cell in src.derive_export.build_cells(conn)
        }
        no_cell_no_bw = 0
        for entry in entries:
            rig = entry["rig"]
            estimate = entry["estimate"]
            if estimate is not None and estimate.get("basis") not in allowed_basis:
                raise AssertionError(
                    f"estimate basis {estimate.get('basis')!r} outside {allowed_basis}"
                )
            has_cell = (rig["key"], top_model, 4) in cells
            if not has_cell and rig.get("bandwidthGBs") is None:
                no_cell_no_bw += 1
                if estimate is not None:
                    raise AssertionError(
                        f"invented estimate for {rig['key']} with no cell and no bandwidth"
                    )
        if not no_cell_no_bw:
            raise AssertionError("no candidate with no cell and no bandwidth to guard")

        missing = client.get("/v1/match/hardware-to-models?rig_key=does-not-exist-xyz")
        if missing.status_code != 404 or "error" not in missing.json():
            raise AssertionError(f"nonexistent rig_key status={missing.status_code} body={missing.json()}")
        invalid_bits = client.get(f"/v1/match/hardware-to-models?rig_key={top_rig}&bits=9")
        if invalid_bits.status_code != 422 or "error" not in invalid_bits.json():
            raise AssertionError(f"bits=9 status={invalid_bits.status_code} body={invalid_bits.json()}")
        missing_model = client.get("/v1/match/model-to-hardware?model_slug=does-not-exist-xyz")
        if missing_model.status_code != 404:
            raise AssertionError(f"nonexistent model_slug status={missing_model.status_code}")

        rigs = client.get("/v1/rigs").json().get("rigs", [])
        if not rigs:
            raise AssertionError("/v1/rigs returned no rigs")
        chat_models = client.get("/v1/models?category=chat").json().get("models", [])
        if not chat_models or any(m["category"] != "chat" for m in chat_models):
            raise AssertionError("/v1/models?category=chat filter broken")
    finally:
        conn.close()


@target("ops")
def check_ops() -> None:
    _import_config()

    import os
    import subprocess

    from fastapi.testclient import TestClient

    from src.main import app

    for script in ("scripts/sync-all.sh", "scripts/run.sh"):
        if not os.path.isfile(script):
            raise AssertionError(f"{script} does not exist")
        if not os.access(script, os.X_OK):
            raise AssertionError(f"{script} is not executable")
        result = subprocess.run(["bash", "-n", script], capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError(f"bash -n {script} failed: {result.stderr}")

    body = TestClient(app).get("/healthz").json()
    if body.get("ok") is not True:
        raise AssertionError(f"healthz ok != true: {body!r}")
    if body.get("runs", 0) <= 0:
        raise AssertionError(f"healthz runs={body.get('runs')}, expected > 0 (run scripts/sync-all.sh)")
    if body.get("lastSyncAt") is None:
        raise AssertionError("healthz lastSyncAt is null (run scripts/sync-all.sh)")


def run(target_name: str) -> None:
    if target_name not in TARGETS:
        valid = ", ".join(sorted(TARGETS))
        sys.stderr.write(f"unknown target {target_name!r}; valid: {valid}\n")
        sys.exit(1)
    TARGETS[target_name]()
    print(f"check: {target_name} OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stderr.write("usage: uv run python scripts/check.py <target>\n")
        sys.exit(1)
    name = sys.argv[1]
    if name == "all":
        for key in sorted(TARGETS):
            run(key)
        sys.exit(0)
    run(name)
