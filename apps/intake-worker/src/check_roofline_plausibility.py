"""Roofline decode plausibility check (plan section 12.3).

Flags ``roofline_violation`` when the reported decode throughput exceeds the
physical memory-bandwidth ceiling predicted by the roofline kernel.
"""

from __future__ import annotations

from estimate_decode_throughput import estimate_decode_tokens_per_second

from worker_models import (
    RunRecord,
    build_gpu_spec,
    build_model_arch,
    build_quant_profile,
    build_scenario,
)

ROOFLINE_HEADROOM = 0.92
ROOFLINE_VIOLATION = "roofline_violation"


def decode_roofline_tokens_per_second(record: RunRecord) -> float:
    return estimate_decode_tokens_per_second(
        build_gpu_spec(record),
        build_model_arch(record),
        build_quant_profile(record),
        build_scenario(record),
    )


def check_roofline_plausibility(record: RunRecord) -> str | None:
    ceiling = ROOFLINE_HEADROOM * decode_roofline_tokens_per_second(record)
    if record.metrics["decode_tok_s"] > ceiling:
        return ROOFLINE_VIOLATION
    return None
