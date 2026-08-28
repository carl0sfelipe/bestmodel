"""Leaderboard query with filtering and ranking (S11).

Validated runs are filtered by hardware/model/runtime/quant/context, checked
for feasibility, scored with the recommendation engine's balanced formula and
returned ranked. Infeasible entries are hidden per plan section 11.10.
"""

from __future__ import annotations

from typing import Any

from calculate_ranking_score import calculate_ranking_score
from filter_feasible_models import filter_feasible_models, mark_feasibility

from src.dependencies.database_session_provider import DatabaseSession

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

_NUMERIC_FIELDS = (
    "decode_tok_s",
    "prefill_tok_s",
    "ttft_ms",
    "peak_vram_mib",
    "power_watt_avg",
    "quality_retention_estimate",
    "trust_score",
    "vram_capacity_mib",
    "seconds_per_clip",
    "it_per_s",
    "frames_per_s",
)


def query_leaderboard(session: DatabaseSession, filters: dict[str, Any],
                      sort: str | None, limit: int | None, offset: int | None) -> dict[str, Any]:
    entries = [_coerce_numeric(entry) for entry in session.fetch_leaderboard_entries()]
    # A cell without a source class never renders (Story 2.1): every leaderboard
    # entry must declare where its number came from.
    entries = [entry for entry in entries if entry.get("source_class")]
    entries = _apply_filters(entries, filters)
    entries = filter_feasible_models(mark_feasibility(entries))
    entries = calculate_ranking_score(entries)
    entries.sort(key=_sort_key(sort), reverse=True)
    safe_limit = max(1, min(limit or DEFAULT_LIMIT, MAX_LIMIT))
    safe_offset = max(0, offset or 0)
    return {"runs": entries[safe_offset : safe_offset + safe_limit]}


def _coerce_numeric(entry: dict[str, Any]) -> dict[str, Any]:
    """Postgres NUMERIC arrives as decimal.Decimal; the ranking engine needs
    native floats."""
    coerced = dict(entry)
    for field in _NUMERIC_FIELDS:
        if coerced.get(field) is not None:
            coerced[field] = float(coerced[field])
    return coerced


def _apply_filters(entries: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    exact_fields = (
        "gpu_model_id",
        "model_release_id",
        "runtime_engine",
        "quantization_profile_id",
        "quant_format",
        "batch_size",
        "source_class",
        "recipe_id",
    )
    filtered = entries
    for field in exact_fields:
        wanted = filters.get(field)
        if wanted is not None:
            filtered = [e for e in filtered if _field_equals(e.get(field), wanted)]
    filtered = _apply_context_bounds(filtered, filters)
    return filtered


def _field_equals(actual: Any, wanted: Any) -> bool:
    if actual is None:
        return False
    if isinstance(actual, int) and not isinstance(actual, bool):
        try:
            return actual == int(wanted)
        except (TypeError, ValueError):
            return False
    return str(actual) == str(wanted)


def _apply_context_bounds(entries: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    minimum = filters.get("context_tokens_min")
    maximum = filters.get("context_tokens_max")
    if minimum is not None:
        entries = [e for e in entries if (e.get("context_tokens") or 0) >= int(minimum)]
    if maximum is not None:
        entries = [e for e in entries if (e.get("context_tokens") or 0) <= int(maximum)]
    return entries


def _sort_key(sort: str | None):
    if sort == "submitted_at":
        return lambda entry: entry.get("submitted_at") or ""
    return lambda entry: entry.get("rank_score") or 0.0
