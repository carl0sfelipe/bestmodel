"""Feasibility filtering before ranking (plan section 11.1).

The recommendation engine always checks feasibility first, then ranks. A
candidate is feasible when its peak memory stays within the usable fraction of
the hardware capacity (section 11.2: peak <= capacity * safety margin).
"""

from __future__ import annotations

from typing import Any

SAFETY_MARGIN = 0.95


def usable_memory_mib(capacity_mib: float) -> float:
    return capacity_mib * SAFETY_MARGIN


def is_feasible(peak_memory_mib: float, capacity_mib: float | None) -> bool:
    """Candidates whose hardware capacity is unknown pass through unfiltered;
    the platform cannot disprove feasibility without a capacity to compare."""
    if capacity_mib is None:
        return True
    return peak_memory_mib <= usable_memory_mib(capacity_mib)


def mark_feasibility(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for candidate in candidates:
        candidate["feasible"] = is_feasible(
            candidate["peak_vram_mib"], candidate.get("vram_capacity_mib")
        )
    return candidates


def filter_feasible_models(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hide infeasible candidates (section 11.10: infeasible items are hidden
    and their rank score is zeroed by the ranking stage)."""
    return [candidate for candidate in candidates if candidate.get("feasible", True)]
