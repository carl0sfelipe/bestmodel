"""localmaxxing.com community-pool importer (S22).

Owner-approved bulk import of self-reported performance cells into the
``run_claim`` table. Imported claims:

- carry ``source='localmaxxing'`` and ``claimant_id = NULL`` (community
  provenance, displayed as "localmaxxing pool");
- NEVER enter validated leaderboards — they are claims until somebody
  proves them with a signed CLI run (the settle flow);
- are frozen with a prior snapshot: the cell's own reported median
  (basis ``reported``) plus our roofline prediction when the GPU resolves.

Conservative by design: only cells whose model maps to our catalog are
imported; everything else is reported as catalog-expansion backlog.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from src.dependencies.database_session_provider import DatabaseSession
from src.services.auth_common import utcnow_iso
from src.services.compute_claim_prior import compute_claim_prior

SOURCE = "localmaxxing"
DISPLAY_HANDLE = "localmaxxing pool"

# bits -> quantization_profile id. GGUF variants assume llama.cpp, the pool's
# dominant engine; unmappable bit counts leave quantization null.
BITS_TO_QUANT: dict[int, str] = {
    16: "q-fp16",
    8: "q-fp8",
    4: "q-gguf-q4-k-m",
    3: "q-gguf-q3-k-m",
    2: "q-gguf-q2-k",
}

SKIP_REASONS = ("nomodel", "nometrics", "multigpu-v1", "existing")

# (normalized alias fragment, gpu_model id) — rig keys whose community naming
# diverges from the marketing names in our catalog.
GPU_RIG_ALIASES: tuple[tuple[str, str], ...] = (
    ("gb10graceblackwell", "gpu-gb10-grace-blackwell"),
    ("gb10", "gpu-gb10-grace-blackwell"),
    ("ryzenaimax395", "gpu-ryzen-ai-max-395"),
    ("rx7900xtx", "gpu-rx-7900-xtx"),
    ("m1max", "gpu-m1-max"),
    ("rtxpro6000blackwell", "gpu-rtx-pro-6000-blackwell"),
    ("gtx1080ti", "gpu-gtx-1080-ti"),
)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


class CatalogIndex:
    """Alias-based matching of external slugs/rig keys onto our catalog."""

    def __init__(self, session: DatabaseSession) -> None:
        self._session = session
        self._quant_ids = {q["id"] for q in session.fetch_quantization_profiles()}
        self._model_aliases = self._build_model_aliases(session.fetch_all_models())
        self._gpu_suffixes = self._build_gpu_suffixes(session.fetch_all_gpus())

    @staticmethod
    def _build_model_aliases(models: list[dict[str, Any]]) -> list[tuple[str, str]]:
        """(normalized alias, model_id), longest first so specific wins."""
        aliases: list[tuple[str, str]] = []
        for model in models:
            for source in (model["release_name"], model["id"].removeprefix("model-")):
                alias = normalize(source)
                if len(alias) >= 6:
                    aliases.append((alias, model["id"]))
        aliases.sort(key=lambda pair: -len(pair[0]))
        return aliases

    @staticmethod
    def _build_gpu_suffixes(gpus: list[dict[str, Any]]) -> list[tuple[str, str]]:
        """(normalized marketing suffix, gpu_id), most specific first."""
        aliases: list[tuple[str, str]] = []
        for gpu in gpus:
            suffix = normalize(gpu["marketing_name"])
            for vendor_word in ("nvidiageforce", "nvidia"):
                if suffix.startswith(vendor_word):
                    suffix = suffix[len(vendor_word):]
                    break
            aliases.append((suffix, gpu["id"]))
        aliases.sort(key=lambda pair: len(pair[0]))
        return aliases

    def match_model(self, slug: str) -> str | None:
        haystack = normalize(slug)
        for alias, model_id in self._model_aliases:
            if alias in haystack:
                return model_id
        return None

    def match_gpu(self, rig_key: str) -> str | None:
        rig = _strip_rig_decorations(rig_key)
        if not rig:
            return None
        # explicit aliases first (rig naming that diverges from marketing names)
        for alias, gpu_id in GPU_RIG_ALIASES:
            if alias in rig or rig in alias:
                return gpu_id
        candidates = [rig, "rtx" + rig, "gtx" + rig]
        for suffix, gpu_id in self._gpu_suffixes:
            for candidate in candidates:
                if suffix == candidate or suffix.startswith(candidate):
                    return gpu_id
        return None

    def quant_known(self, quant_id: str) -> bool:
        return quant_id in self._quant_ids


def _strip_rig_decorations(rig_key: str) -> str:
    rig = re.sub(r"-x\d+$", "", rig_key)
    rig = re.sub(r"-\d+gb$", "", rig)
    return normalize(rig)


def external_ref_for(cell: dict[str, Any]) -> str:
    """Quantization is part of the identity: same rig+model at different
    bit widths are distinct claims."""
    return f"{SOURCE}:{cell['rigKey']}:{cell['modelSlug']}:{cell.get('bits')}"


def note_for(cell: dict[str, Any]) -> str:
    engines = ", ".join(cell.get("engines") or [])
    return (
        f"median of {cell.get('n', 1)} self-reported run(s) via localmaxxing.com "
        f"(owner-approved); ~{cell.get('bits')}-bit weights; engines: {engines}; "
        f"rig: {cell['rigKey']}"
    )


def build_claim_record(
    index: CatalogIndex, cell: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Map one pool cell to a run_claim record; returns (record, skip_reason)."""
    rig_key = cell.get("rigKey") or ""
    if re.search(r"-x\d+$", rig_key):
        return None, "multigpu-v1"
    decode = cell.get("tokSOutMedian")
    if decode is None:
        return None, "nometrics"

    model_id = index.match_model(cell.get("modelSlug") or "")
    if model_id is None:
        return None, "nomodel"

    gpu_id = index.match_gpu(rig_key)
    quant_id = BITS_TO_QUANT.get(int(cell.get("bits") or 0))
    if quant_id is not None and not index.quant_known(quant_id):
        quant_id = None

    now = utcnow_iso()
    return (
        {
            "id": str(uuid.uuid4()),
            "claimant_id": None,
            "source": SOURCE,
            "external_ref": external_ref_for(cell),
            "rig_id": None,
            "model_release_id": model_id,
            "quantization_profile_id": quant_id,
            "inference_runtime_id": None,
            "gpu_model_id": gpu_id,
            "context_tokens": cell.get("maxContextTested"),
            "claimed_metrics": _claimed_metrics(cell),
            "note": note_for(cell),
            "status": "open",
            "prior_snapshot": {},  # frozen prior filled by import_cells
            "created_at": now,
            "updated_at": now,
        },
        None,
    )


def _claimed_metrics(cell: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {"decode_tok_s": cell["tokSOutMedian"]}
    if cell.get("tokSPrefillMedian") is not None:
        metrics["prefill_tok_s"] = cell["tokSPrefillMedian"]
    if cell.get("ttftMsMedian") is not None:
        metrics["ttft_ms"] = cell["ttftMsMedian"]
    if cell.get("peakVramGbMedian") is not None:
        metrics["peak_vram_mib"] = round(cell["peakVramGbMedian"] * 1024)
    return metrics


def import_cells(
    session: DatabaseSession,
    cells: list[dict[str, Any]],
    *,
    dry_run: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    """Import pool cells; returns stats. ``dry_run`` never writes."""
    index = CatalogIndex(session)
    stats: dict[str, Any] = {reason: 0 for reason in SKIP_REASONS}
    stats["imported"] = 0
    stats["total"] = len(cells)
    stats["unmapped_models"] = {}

    selected = cells[:limit] if limit else cells
    for cell in selected:
        ref = external_ref_for(cell)
        if session.find_run_claim_by_external_ref(ref) is not None:
            stats["existing"] += 1
            continue

        record, skip = build_claim_record(index, cell)
        if record is None:
            stats[skip] += 1
            if skip == "nomodel":
                slug = cell.get("modelSlug") or "?"
                stats["unmapped_models"][slug] = (
                    stats["unmapped_models"].get(slug, 0) + 1
                )
            continue

        record["prior_snapshot"] = _frozen_prior(session, record, cell)
        if not dry_run:
            session.insert_run_claim(record)
        stats["imported"] += 1

    if not dry_run:
        session.commit()
    stats["unmapped_models"] = dict(
        sorted(stats["unmapped_models"].items(), key=lambda kv: -kv[1])[:15]
    )
    return stats


def _frozen_prior(
    session: DatabaseSession, record: dict[str, Any], cell: dict[str, Any]
) -> dict[str, Any]:
    prior = compute_claim_prior(
        session,
        record["model_release_id"],
        record.get("quantization_profile_id"),
        record.get("gpu_model_id"),
        record.get("context_tokens"),
    )
    # The cell's own reported median is the honest pool signal at import
    # time; it overwrites the (empty) measured-pool lookup.
    prior["pool"] = {
        "basis": "reported",
        "source": SOURCE,
        "model_release_id": record["model_release_id"],
        "quantization_profile_id": record.get("quantization_profile_id"),
        "run_count": int(cell.get("n") or 1),
        "p50_decode_tok_s": cell.get("tokSOutMedian"),
        "p50_prefill_tok_s": cell.get("tokSPrefillMedian"),
    }
    return prior
