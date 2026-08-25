"""S5 — decision engine: server-side mirror of the web pack engine (CONTRATO
web §5/§6). Pure functions over web-schema objects (Rig, DerivedModel, Cell)
as produced by src.derive_export from the clean SQLite pool (impossible runs
excluded, same rule as S4). Same constants, same honesty ladder: measured >
reported > extrapolated > null.
"""

from src.config import (
    CTX_ALLOWANCE_GB,
    FIT_OK,
    FIT_TIGHT,
    GB_PER_B_PER_BIT,
    MIN_RUNS_MEASURED,
    USABLE_DISCRETE,
    USABLE_UNIFIED,
)
from src.derive_export import round2

BASIS_WEIGHT = {"measured": 3, "reported": 2, "extrapolated": 1}


def usable_mem_gb(rig: dict) -> float | None:
    """GPU-addressable memory: 0.90 discrete/CPU_ONLY, 0.75 unified (web §5)."""
    if rig["memGb"] is None:
        return None
    fraction = USABLE_UNIFIED if rig["hwClass"] == "UNIFIED" else USABLE_DISCRETE
    return rig["memGb"] * fraction


def vram_needed_gb(model: dict, bits: int) -> dict | None:
    """VRAM needed: measured median (n>=2) wins, else formula. MoE uses TOTAL
    params (weights are resident), so paramsB is the only source either way."""
    if bits is None:
        return None
    measured = model["vramMeasuredGb"].get(str(bits))
    if measured and measured["n"] >= 2:
        return {"gb": measured["gb"], "basis": "measured"}
    if model["paramsB"] is None:
        return None
    return {
        "gb": round2(GB_PER_B_PER_BIT * bits * model["paramsB"] + CTX_ALLOWANCE_GB),
        "basis": "formula",
    }


def fit_class(rig: dict, model: dict, bits: int) -> str | None:
    """'no' | 'tight' | 'ok' | 'head' | None by usable-vs-needed headroom (web §5)."""
    usable = usable_mem_gb(rig)
    need = vram_needed_gb(model, bits)
    if usable is None or need is None:
        return None
    if need["gb"] > usable:
        return "no"
    headroom = (usable - need["gb"]) / usable
    if headroom < FIT_TIGHT:
        return "tight"
    if headroom < FIT_OK:
        return "ok"
    return "head"


def _exact_cell(cells: list[dict], rig_key: str, model_slug: str, bits: int) -> dict | None:
    for cell in cells:
        if (
            cell["rigKey"] == rig_key
            and cell["modelSlug"] == model_slug
            and cell["bits"] == bits
        ):
            return cell
    return None


def estimate_tok_s(
    rig: dict, model: dict, bits: int, cells: list[dict], rigs: list[dict]
) -> dict | None:
    """Speed ladder (web §5): exact cell -> measured/reported; else linear
    bandwidth scaling from the best other-rig cell; else None (never invent)."""
    if bits is None:
        return None
    exact = _exact_cell(cells, rig["key"], model["slug"], bits)
    if exact is not None:
        return {
            "value": exact["tokSOutMedian"],
            "basis": "measured" if exact["n"] >= MIN_RUNS_MEASURED else "reported",
            "n": exact["n"],
        }
    if rig["bandwidthGBs"] is None:
        return None
    bw_by_key = {other["key"]: other["bandwidthGBs"] for other in rigs}
    sources = sorted(
        (
            cell
            for cell in cells
            if cell["modelSlug"] == model["slug"]
            and cell["bits"] == bits
            and cell["rigKey"] != rig["key"]
            and bw_by_key.get(cell["rigKey"]) is not None
        ),
        key=lambda cell: (-cell["n"], cell["rigKey"]),
    )
    if not sources:
        return None
    source = sources[0]
    return {
        "value": round2(
            source["tokSOutMedian"] * (rig["bandwidthGBs"] / bw_by_key[source["rigKey"]])
        ),
        "basis": "extrapolated",
        "n": source["n"],
    }


def _better(a: dict, b: dict) -> bool:
    """True if a outranks b: basis weight desc, tok/s desc, slug asc, bits asc."""
    dw = BASIS_WEIGHT[a["est"]["basis"]] - BASIS_WEIGHT[b["est"]["basis"]]
    if dw != 0:
        return dw > 0
    if a["est"]["value"] != b["est"]["value"]:
        return a["est"]["value"] > b["est"]["value"]
    if a["model"]["slug"] != b["model"]["slug"]:
        return a["model"]["slug"] < b["model"]["slug"]
    return a["bits"] < b["bits"]


def _rank_key(pick: dict):
    """Sort key equivalent to _better (web §5 topPicks ordering)."""
    return (
        -BASIS_WEIGHT[pick["est"]["basis"]],
        -pick["est"]["value"],
        pick["model"]["slug"],
        pick["bits"],
    )


def top_picks(
    rig: dict, models: list[dict], cells: list[dict], rigs: list[dict], k: int
) -> list[dict]:
    """Best ok/head candidate per model with a non-null estimate, ranked web-style."""
    bits_by_model: dict[str, set[int]] = {}
    for cell in cells:
        bits_by_model.setdefault(cell["modelSlug"], set()).add(cell["bits"])

    picks = []
    for model in models:
        best = None
        for bits in sorted(bits_by_model.get(model["slug"], [])):
            fit = fit_class(rig, model, bits)
            if fit not in ("ok", "head"):
                continue
            est = estimate_tok_s(rig, model, bits, cells, rigs)
            if est is None:
                continue
            candidate = {"model": model, "bits": bits, "fit": fit, "est": est}
            if best is None or _better(candidate, best):
                best = candidate
        if best is not None:
            picks.append(best)

    picks.sort(key=_rank_key)
    return picks[:k]


def model_to_hardware(
    model: dict, rigs: list[dict], cells: list[dict], bits: int, k: int
) -> list[dict]:
    """Pool rigs that hold (model, bits): with a cell OR fit ok/head by formula,
    ranked like top_picks (basis weight desc, then tok/s desc). estimate is null
    when there is no cell and no bandwidth — never an invented number."""
    candidates = []
    for rig in rigs:
        has_cell = _exact_cell(cells, rig["key"], model["slug"], bits) is not None
        fit = fit_class(rig, model, bits)
        if not (has_cell or fit in ("ok", "head")):
            continue
        candidates.append(
            {
                "rig": rig,
                "bits": bits,
                "fit": fit,
                "est": estimate_tok_s(rig, model, bits, cells, rigs),
            }
        )
    candidates.sort(
        key=lambda entry: (
            -(BASIS_WEIGHT[entry["est"]["basis"]] if entry["est"] else 0),
            -(entry["est"]["value"] if entry["est"] else float("-inf")),
            entry["rig"]["key"],
        )
    )
    return candidates[:k]
