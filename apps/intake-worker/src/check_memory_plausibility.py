"""Memory footprint plausibility check (plan section 12.3).

Flags ``impossible_memory_footprint`` when the reported peak VRAM falls below
the minimum footprint the roofline kernel estimates for the configuration.
"""

from __future__ import annotations

from roofline_kernel import estimate_vram_footprint

from worker_models import (
    RunRecord,
    build_gpu_spec,
    build_model_arch,
    build_quant_profile,
    build_scenario,
)

MEMORY_FLOOR_FRACTION = 0.80
MIB_IN_BYTES = 1048576
IMPOSSIBLE_MEMORY_FOOTPRINT = "impossible_memory_footprint"


def minimum_vram_mib(record: RunRecord) -> float:
    model = build_model_arch(record)
    quant = build_quant_profile(record)
    scenario = build_scenario(record)
    footprint = estimate_vram_footprint(
        model=model,
        parameter_count=model.parameter_count_billion * 1e9,
        num_layers=model.num_layers,
        num_kv_heads=model.num_kv_heads,
        head_dim=model.head_dim,
        weight_bits=quant.weight_bits,
        kv_cache_bytes_per_element=quant.kv_cache_bits / 8.0,
        context_tokens=scenario.context_tokens,
        batch_size=scenario.batch_size,
        runtime=record.runtime_engine,
        vram_capacity_mib=build_gpu_spec(record).vram_mib,
    )
    return footprint.peak_vram_bytes / MIB_IN_BYTES


def check_memory_plausibility(record: RunRecord) -> str | None:
    floor_mib = MEMORY_FLOOR_FRACTION * minimum_vram_mib(record)
    if record.metrics["peak_vram_mib"] < floor_mib:
        return IMPOSSIBLE_MEMORY_FOOTPRINT
    return None
