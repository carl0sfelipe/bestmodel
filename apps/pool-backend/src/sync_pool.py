"""Sync the localmaxxing public pool into the local SQLite database.

Executable via `uv run python -m src.sync_pool`. Idempotent: upserts by
primary key, never recreates the database. Identity normalization (rigKey,
model slug, quant->bits) and the bandwidth seed mirror the web pack
(CONTRATO web §4/§6) so results match byte-for-byte.

Guards (spec S2): stop and ask if the remote total < 4500 or if more than
30% of approved runs have no quant bits.
"""

import json
import math
import re
import sqlite3
import time
from datetime import datetime, timezone

import httpx

from src.config import API_BASE, DB_PATH, THROTTLE_MS, USER_AGENT
from src.db import connect, migrate

SPEED_TEST_LIMIT = 100
MODELS_LIMIT = 200
MAX_ATTEMPTS = 3
RETRY_BACKOFF_S = 2.0
REQUEST_TIMEOUT_S = 30.0
MIN_REMOTE_TOTAL = 4500
MAX_NULL_BITS_FRACTION = 0.30

BANDWIDTH_SEED_GBS = {
    "RTX 3090": 936.2,
    "RTX 3060": 360,
    "Ryzen AI Max 395": 256,
    "GB10 Grace Blackwell": 273,
    "RTX 3060 Ti": 448,
    "RTX 5090": 1792,
    "RX 7900 XTX": 960,
    "RTX 4070": 504,
    "M3 Ultra": 800,
    "RTX 4090": 1008,
}


def slugify(s: str) -> str:
    """Web pack slugify: lowercase, [^a-z0-9]+ -> '-', trim hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def quant_bits(quant: str | None) -> int | None:
    """Quant string -> bit width, mirroring web §6 quantBits."""
    if not quant:
        return None
    q = quant.strip()
    if re.fullmatch(r"fp16|bf16|f16", q, re.I):
        return 16
    if re.fullmatch(r"fp8", q, re.I):
        return 8
    if re.fullmatch(r"awq|gptq", q, re.I):
        return 4
    match = re.search(r"[1-8]", q)
    return int(match.group(0)) if match else None


def _first_not_none(*values):
    """Emulate JS `??`: first value that is not None, else None."""
    for value in values:
        if value is not None:
            return value
    return None


def _js_num(value) -> str:
    """Format a number the way JS Number.toString() does (24 -> '24')."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def normalize_gpu_name(raw: str | None) -> str:
    """nomeNorm (DISCRETE): strip vendor prefixes, then trailing size suffix."""
    name = (raw or "").strip()
    while True:
        prev = name
        name = re.sub(r"^(NVIDIA|AMD|Intel|GeForce)\s+", "", name, count=1, flags=re.I)
        if name == prev:
            break
    return re.sub(r"\s+\d+(\.\d+)?\s*GB$", "", name, flags=re.I).strip()


def unified_canonical_name(hw: dict) -> str:
    """nomeCanonico (UNIFIED): GB10 / Ryzen AI Max 3xx / variant fallback."""
    variant = hw.get("chipVariant")
    family = hw.get("chipFamily")
    text = f"{'' if variant is None else variant} {'' if family is None else family}"
    if re.search(r"gb10|dgx\s*spark", text, re.I):
        return "GB10 Grace Blackwell"
    if re.search(r"ryzen|strix|ai\s*max", text, re.I):
        if re.search(r"395", text):
            return "Ryzen AI Max 395"
        if re.search(r"385", text):
            return "Ryzen AI Max 385"
    return _first_not_none(variant, family, "unknown").strip()


def build_vram_modals(runs: list[dict]) -> dict[str, float]:
    """Modal vramGb per nomeNorm over gpu_count==1 discrete runs."""
    counts: dict[str, dict[float, int]] = {}
    for run in runs:
        hw = run["hardware"]
        if hw.get("hwClass") != "DISCRETE_GPU":
            continue
        if (hw.get("gpuCount") or 1) != 1 or hw.get("vramGb") is None:
            continue
        name = normalize_gpu_name(hw.get("gpuName"))
        per_name = counts.setdefault(name, {})
        per_name[hw["vramGb"]] = per_name.get(hw["vramGb"], 0) + 1
    modals = {}
    for name, per_name in counts.items():
        best = sorted(per_name.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)[0]
        modals[name] = best[0]
    return modals


def per_card_vram(hw: dict, modals: dict[str, float], name: str) -> float | None:
    """vramPorPlaca: modal normalization (total reported -> per card) else round."""
    vram = hw.get("vramGb")
    count = hw.get("gpuCount") or 1
    modal = modals.get(name)
    if vram is None:
        return None
    if modal is not None:
        if count > 1 and abs(vram - modal * count) <= 1:
            return modal
        if abs(vram - modal) <= 2:
            return modal
    return math.floor(vram + 0.5)


def rig_identity(hw: dict, modals: dict[str, float]) -> dict:
    """Rig key/label/bandwidth inputs, mirroring web derive rigIdentity."""
    count = hw.get("gpuCount") or 1
    if hw.get("hwClass") == "DISCRETE_GPU":
        name = normalize_gpu_name(hw.get("gpuName"))
        per_card = per_card_vram(hw, modals, name)
        per_key = "na" if per_card is None else _js_num(per_card)
        per_label = "?" if per_card is None else _js_num(per_card)
        suffix = f" x{count}" if count > 1 else ""
        return {
            "key": slugify(f"{name} {per_key}gb{suffix}"),
            "label": f"{name} {per_label}GB" + (f" \u00d7{count}" if count > 1 else ""),
            "match_name": name,
            "mem_gb": None if per_card is None else per_card * count,
            "gpu_count": count,
        }
    if hw.get("hwClass") == "UNIFIED":
        name = unified_canonical_name(hw)
        mem = hw.get("unifiedMemoryGb")
        mem_key = "na" if mem is None else _js_num(mem)
        mem_label = "?" if mem is None else _js_num(mem)
        return {
            "key": slugify(f"{name} {mem_key}gb"),
            "label": f"{name} {mem_label}GB",
            "match_name": name,
            "mem_gb": mem,
            "gpu_count": 1,
        }
    cpu = _first_not_none(hw.get("cpu"), "unknown").strip()
    return {
        "key": slugify(f"cpu {cpu}"),
        "label": cpu,
        "match_name": cpu,
        "mem_gb": hw.get("ramGb"),
        "gpu_count": 1,
    }


def seed_bandwidth(identity: dict, hw_class: str) -> float | None:
    """Bandwidth from the web §6 seed; substring, longest-name, gpu_count==1."""
    if hw_class == "CPU_ONLY" or identity["gpu_count"] > 1:
        return None
    match_name = identity["match_name"].lower()
    matches = [name for name in BANDWIDTH_SEED_GBS if name.lower() in match_name]
    if not matches:
        return None
    matches.sort(key=len, reverse=True)
    return BANDWIDTH_SEED_GBS[matches[0]]


def model_category(display_name: str) -> str:
    return "code" if re.search(r"coder|starcoder|codestral|code", display_name, re.I) else "chat"


def _compact(raw: dict) -> str:
    return json.dumps(raw, ensure_ascii=False, separators=(",", ":"))


def _real_or_none(value) -> float | None:
    """Coerce to float for a REAL column; non-numeric -> NULL (no inventing)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _eval_score_value(raw: dict) -> float | None:
    """evalScore may be number|null (contract §3) or {score,...} on the wire
    (44/689 models; web pack ships these objects in models.json). Store the
    numeric score; NULL otherwise."""
    value = raw.get("evalScore")
    if isinstance(value, dict):
        value = value.get("score")
    return _real_or_none(value)


def model_row_from_catalog(raw: dict) -> dict:
    return {
        "slug": slugify(raw["hfId"]),
        "hf_id": raw["hfId"],
        "display_name": raw["displayName"],
        "family": raw.get("family"),
        "params_b": _real_or_none(raw.get("params")),
        "active_params_b": _real_or_none(raw.get("activeParams")),
        "is_moe": 1 if raw.get("isMoE") else 0,
        "category": model_category(raw["displayName"]),
        "eval_score": _eval_score_value(raw),
        "raw_json": _compact(raw),
    }


def model_row_from_run_model(run_model: dict) -> dict:
    """Fallback row for a run model absent from the catalog (web derive logic)."""
    display = run_model.get("displayName") or ""
    return {
        "slug": slugify(run_model["hfId"]),
        "hf_id": run_model["hfId"],
        "display_name": display,
        "family": run_model.get("family"),
        "params_b": _real_or_none(run_model.get("params")),
        "active_params_b": None,
        "is_moe": 0,
        "category": model_category(display),
        "eval_score": None,
        "raw_json": _compact(run_model),
    }


def run_row(run: dict, rig_key: str, model_slug: str) -> dict:
    engine = run.get("engine") or {}
    flags = run.get("engineFlags") or {}
    return {
        "id": run["id"],
        "model_slug": model_slug,
        "rig_key": rig_key,
        "bits": quant_bits(engine.get("quantization")),
        "quant": engine.get("quantization"),
        "engine": engine.get("engineName"),
        "tok_s_out": run["tokSOut"],
        "tok_s_prefill": run.get("tokSPrefill"),
        "ttft_ms": run.get("ttftMs"),
        "peak_vram_gb": run.get("peakVramGb"),
        "context_length": run.get("contextLength"),
        "batch_size": run.get("batchSize"),
        "spec_decoding": 1 if flags.get("specDecoding") else 0,
        "mtp_enabled": 1 if flags.get("mtpEnabled") else 0,
        "concurrency": flags.get("concurrency"),
        "created_at": run.get("createdAt") or "",
        "raw_json": _compact(run),
    }


def _get_json(client: httpx.Client, path: str) -> dict | list:
    url = f"{API_BASE}{path}"
    for attempt in range(MAX_ATTEMPTS):
        response = client.get(url)
        if response.status_code == 200:
            return response.json()
        if attempt == MAX_ATTEMPTS - 1:
            raise RuntimeError(f"FATAL: {url} -> HTTP {response.status_code} after retries")
        print(f"retry {attempt + 1} for {path} (HTTP {response.status_code})")
        time.sleep(RETRY_BACKOFF_S)
    raise RuntimeError(f"unreachable: {url}")


def fetch_speed_tests(client: httpx.Client) -> tuple[int, list[dict]]:
    collected: list[dict] = []
    offset = 0
    remote_total = float("inf")
    while offset < remote_total:
        page = _get_json(client, f"/speed-tests?limit={SPEED_TEST_LIMIT}&offset={offset}")
        remote_total = page["total"]
        collected.extend(page["speedTests"])
        offset += SPEED_TEST_LIMIT
        print(f"speed-tests {min(offset, remote_total)}/{remote_total}")
        time.sleep(THROTTLE_MS / 1000)
    deduped = {item["id"]: item for item in collected}
    return remote_total, list(deduped.values())


def fetch_models(client: httpx.Client) -> list[dict]:
    collected: list[dict] = []
    offset = 0
    while True:
        page = _get_json(client, f"/models?limit={MODELS_LIMIT}&offset={offset}")
        collected.extend(page)
        offset += MODELS_LIMIT
        print(f"models {len(collected)}")
        time.sleep(THROTTLE_MS / 1000)
        if len(page) < MODELS_LIMIT:
            break
    deduped = {item["id"]: item for item in collected}
    return list(deduped.values())


def upsert_models(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        """INSERT INTO lm_model
           (slug, hf_id, display_name, family, params_b, active_params_b,
            is_moe, category, eval_score, raw_json)
           VALUES (:slug, :hf_id, :display_name, :family, :params_b, :active_params_b,
            :is_moe, :category, :eval_score, :raw_json)
           ON CONFLICT(slug) DO UPDATE SET
             hf_id=excluded.hf_id, display_name=excluded.display_name,
             family=excluded.family, params_b=excluded.params_b,
             active_params_b=excluded.active_params_b, is_moe=excluded.is_moe,
             category=excluded.category, eval_score=excluded.eval_score,
             raw_json=excluded.raw_json""",
        rows,
    )


def upsert_rigs(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        """INSERT INTO lm_rig
           (key, label, hw_class, mem_gb, gpu_count, bandwidth_gbs, run_count)
           VALUES (:key, :label, :hw_class, :mem_gb, :gpu_count, :bandwidth_gbs, 0)
           ON CONFLICT(key) DO UPDATE SET
             label=excluded.label, hw_class=excluded.hw_class,
             mem_gb=excluded.mem_gb, gpu_count=excluded.gpu_count,
             bandwidth_gbs=excluded.bandwidth_gbs""",
        rows,
    )


def upsert_runs(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        """INSERT INTO lm_run
           (id, model_slug, rig_key, bits, quant, engine, tok_s_out, tok_s_prefill,
            ttft_ms, peak_vram_gb, context_length, batch_size, spec_decoding,
            mtp_enabled, concurrency, created_at, raw_json)
           VALUES (:id, :model_slug, :rig_key, :bits, :quant, :engine, :tok_s_out,
            :tok_s_prefill, :ttft_ms, :peak_vram_gb, :context_length, :batch_size,
            :spec_decoding, :mtp_enabled, :concurrency, :created_at, :raw_json)
           ON CONFLICT(id) DO UPDATE SET
             model_slug=excluded.model_slug, rig_key=excluded.rig_key,
             bits=excluded.bits, quant=excluded.quant, engine=excluded.engine,
             tok_s_out=excluded.tok_s_out, tok_s_prefill=excluded.tok_s_prefill,
             ttft_ms=excluded.ttft_ms, peak_vram_gb=excluded.peak_vram_gb,
             context_length=excluded.context_length, batch_size=excluded.batch_size,
             spec_decoding=excluded.spec_decoding, mtp_enabled=excluded.mtp_enabled,
             concurrency=excluded.concurrency, created_at=excluded.created_at,
             raw_json=excluded.raw_json""",
        rows,
    )


def set_meta(conn: sqlite3.Connection, values: dict[str, str]) -> None:
    conn.executemany(
        "INSERT INTO sync_meta(key, value) VALUES (:key, :value) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        [{"key": key, "value": value} for key, value in values.items()],
    )


def main() -> None:
    conn = connect()
    migrate(conn)

    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_S
    ) as client:
        remote_total, speed_tests = fetch_speed_tests(client)
        raw_models = fetch_models(client)

    runs = [
        run
        for run in speed_tests
        if run.get("status") == "APPROVED" and (run.get("tokSOut") or 0) > 0
    ]

    if remote_total < MIN_REMOTE_TOTAL:
        raise RuntimeError(
            f"remote total {remote_total} < {MIN_REMOTE_TOTAL}: pool too small, stop and ask"
        )

    no_bits = sum(
        1
        for run in runs
        if quant_bits((run.get("engine") or {}).get("quantization")) is None
    )
    if runs and no_bits / len(runs) > MAX_NULL_BITS_FRACTION:
        raise RuntimeError(
            f"{no_bits}/{len(runs)} runs without bits "
            f"(>{MAX_NULL_BITS_FRACTION:.0%}): quant table insufficient, stop and ask"
        )

    modals = build_vram_modals(runs)

    model_rows = {slugify(m["hfId"]): model_row_from_catalog(m) for m in raw_models}
    rig_rows: dict[str, dict] = {}
    run_rows: list[dict] = []

    for run in runs:
        model_slug = slugify(run["model"]["hfId"])
        if model_slug not in model_rows:
            model_rows[model_slug] = model_row_from_run_model(run["model"])
        identity = rig_identity(run["hardware"], modals)
        if identity["key"] not in rig_rows:
            rig_rows[identity["key"]] = {
                "key": identity["key"],
                "label": identity["label"],
                "hw_class": run["hardware"]["hwClass"],
                "mem_gb": identity["mem_gb"],
                "gpu_count": identity["gpu_count"],
                "bandwidth_gbs": seed_bandwidth(identity, run["hardware"]["hwClass"]),
            }
        run_rows.append(run_row(run, identity["key"], model_slug))

    conn.execute("BEGIN")
    upsert_models(conn, list(model_rows.values()))
    upsert_rigs(conn, list(rig_rows.values()))
    upsert_runs(conn, run_rows)
    conn.execute(
        """UPDATE lm_rig SET run_count = (
            SELECT COUNT(*) FROM lm_run WHERE lm_run.rig_key = lm_rig.key
        )"""
    )
    set_meta(
        conn,
        {
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
            "remote_total": str(remote_total),
            "synced_runs": str(len(run_rows)),
        },
    )
    conn.commit()

    print(
        f"synced: {len(run_rows)} runs, {len(rig_rows)} rigs, "
        f"{len(model_rows)} models (remote total {remote_total})"
    )


if __name__ == "__main__":
    main()
