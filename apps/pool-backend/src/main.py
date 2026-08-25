"""FastAPI app (CONTRATO §7): /healthz, catalog lists, and the decision endpoints.

Every request reads the SQLite pool freshly (one cells query per request, no
cross-request cache); impossible runs are excluded exactly like the S4 derived
export. Errors are JSON {"error": ...} including the offending value.
"""

import sqlite3

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.config import BITS_DOMAIN
from src.db import connect
from src.derive_export import build_cells, build_models, build_rigs
from src.match import model_to_hardware, top_picks
from src.plausibility import summary

app = FastAPI(title="bestmodel-backend")

CLEAN_RUN_COUNT_SQL = """SELECT COUNT(*) FROM lm_run r
    JOIN plausibility_flag p ON p.run_id = r.id
    WHERE r.rig_key = ? AND p.verdict != 'impossible'"""


def _json_error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


def _load_rig(conn, rigs: list[dict], rig_key: str) -> dict | None:
    """Web §4 Rig object for rig_key (falls back to the DB row for rigs with
    no clean runs, which build_rigs skips)."""
    for rig in rigs:
        if rig["key"] == rig_key:
            return rig
    row = conn.execute(
        "SELECT key, label, hw_class, mem_gb, gpu_count, bandwidth_gbs "
        "FROM lm_rig WHERE key = ?",
        (rig_key,),
    ).fetchone()
    if row is None:
        return None
    return {
        "key": row["key"],
        "label": row["label"],
        "hwClass": row["hw_class"],
        "memGb": row["mem_gb"],
        "gpuCount": row["gpu_count"],
        "bandwidthGBs": row["bandwidth_gbs"],
        "runCount": conn.execute(CLEAN_RUN_COUNT_SQL, (rig_key,)).fetchone()[0],
    }


def _load_model(conn, models: list[dict], model_slug: str) -> dict | None:
    """Web §4 DerivedModel object for model_slug (DB-row fallback for models
    with no clean runs, so formula-only matching still works)."""
    for model in models:
        if model["slug"] == model_slug:
            return model
    row = conn.execute(
        """SELECT slug, hf_id, display_name, family, params_b, active_params_b,
                  is_moe, category, eval_score
           FROM lm_model WHERE slug = ?""",
        (model_slug,),
    ).fetchone()
    if row is None:
        return None
    return {
        "slug": row["slug"],
        "hfId": row["hf_id"],
        "displayName": row["display_name"],
        "family": row["family"],
        "paramsB": row["params_b"],
        "activeParamsB": row["active_params_b"],
        "isMoE": bool(row["is_moe"]),
        "category": row["category"],
        "runCount": 0,
        "medianTokS": None,
        "evalScore": row["eval_score"],
        "vramMeasuredGb": {},
        "maxContextTested": None,
    }


@app.get("/healthz")
def healthz() -> dict:
    conn = connect()
    try:
        try:
            runs = conn.execute("SELECT COUNT(*) FROM lm_run").fetchone()[0]
            row = conn.execute(
                "SELECT value FROM sync_meta WHERE key = 'last_sync_at'"
            ).fetchone()
        except sqlite3.OperationalError:
            runs = 0
            row = None
    finally:
        conn.close()
    return {"ok": True, "runs": runs, "lastSyncAt": row["value"] if row else None}


@app.get("/v1/plausibility/summary")
def plausibility_summary() -> dict:
    return summary()


@app.get("/v1/rigs")
def list_rigs() -> dict:
    conn = connect()
    try:
        return {"rigs": build_rigs(conn)}
    finally:
        conn.close()


@app.get("/v1/models")
def list_models(category: str | None = None) -> dict:
    conn = connect()
    try:
        models = build_models(conn)
    finally:
        conn.close()
    if category is not None:
        if category not in ("chat", "code"):
            return _json_error(422, f"invalid category {category!r}")
        models = [model for model in models if model["category"] == category]
    return {"models": models}


@app.get("/v1/match/hardware-to-models")
def v1_hardware_to_models(rig_key: str, bits: int = 4, k: int = 10) -> dict:
    if bits not in BITS_DOMAIN:
        return _json_error(422, f"bits {bits} outside domain {sorted(BITS_DOMAIN)}")
    if k < 1:
        return _json_error(422, f"k {k} must be >= 1")
    conn = connect()
    try:
        rigs = build_rigs(conn)
        rig = _load_rig(conn, rigs, rig_key)
        if rig is None:
            return _json_error(404, f"rig_key {rig_key!r} not found")
        models = build_models(conn)
        cells = build_cells(conn)
        picks = top_picks(rig, models, cells, rigs, k)
    finally:
        conn.close()
    return {
        "rig": rig,
        "picks": [
            {
                "model": pick["model"],
                "bits": pick["bits"],
                "fit": pick["fit"],
                "estimate": pick["est"],
            }
            for pick in picks
        ],
    }


@app.get("/v1/match/model-to-hardware")
def v1_model_to_hardware(model_slug: str, bits: int = 4, k: int = 10) -> dict:
    if bits not in BITS_DOMAIN:
        return _json_error(422, f"bits {bits} outside domain {sorted(BITS_DOMAIN)}")
    if k < 1:
        return _json_error(422, f"k {k} must be >= 1")
    conn = connect()
    try:
        rigs = build_rigs(conn)
        models = build_models(conn)
        cells = build_cells(conn)
        model = _load_model(conn, models, model_slug)
        if model is None:
            return _json_error(404, f"model_slug {model_slug!r} not found")
        matches = model_to_hardware(model, rigs, cells, bits, k)
    finally:
        conn.close()
    return {
        "model": model,
        "rigs": [
            {
                "rig": entry["rig"],
                "bits": entry["bits"],
                "fit": entry["fit"],
                "estimate": entry["est"],
            }
            for entry in matches
        ],
    }
