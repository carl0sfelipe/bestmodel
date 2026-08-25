"""VRAM footprint estimation kernel (plan section 11.2).

Implements the weight, KV cache and runtime overhead formulas and the
feasibility check VRAM_peak <= VRAM_capacity * 0.95.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from model_arch import ModelArch, ModelArchitecture

BITS_PER_BYTE = 8
KV_CACHE_COPIES = 2
DEFAULT_ETA_PACK = 1.05
SAFETY_MARGIN = 0.95
RUNTIME_OVERHEAD_FRACTION = 0.05
MIB_BYTES = 2**20
GIB_BYTES = 2**30
DEFAULT_RUNTIME_BASE_OVERHEAD_GIB = 1.5
RUNTIME_BASE_OVERHEAD_GIB = {"llama_cpp": 0.8, "vllm": 2.0}


@dataclass(frozen=True)
class VramFootprint:
    weight_bytes: float
    kv_bytes_per_token: float
    kv_cache_bytes: float
    runtime_overhead_bytes: float
    peak_vram_bytes: float
    vram_capacity_bytes: int

    @property
    def peak_vram_gib(self) -> float:
        return self.peak_vram_bytes / GIB_BYTES

    @property
    def is_feasible(self) -> bool:
        return self.peak_vram_bytes <= self.vram_capacity_bytes * SAFETY_MARGIN


def runtime_base_overhead_gib(runtime: str) -> float:
    return RUNTIME_BASE_OVERHEAD_GIB.get(runtime, DEFAULT_RUNTIME_BASE_OVERHEAD_GIB)


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name}={value}, expected > 0")


def _derive_active_parameter_count(
    model: ModelArch,
    parameter_count: float,
    parameter_count_per_expert: Optional[float],
) -> float:
    if model.active_parameter_count_billion is not None:
        return model.active_parameter_count_billion * 1e9
    if parameter_count_per_expert is None or model.expert_count is None or model.experts_per_token is None:
        raise ValueError("moe active weights require parameter_count_per_expert, expert_count and experts_per_token")
    shared = parameter_count - parameter_count_per_expert * model.expert_count
    return shared + parameter_count_per_expert * model.experts_per_token


def derive_weight_bytes(
    parameter_count: float,
    weight_bits: float,
    eta_pack: float,
    model: Optional[ModelArch] = None,
    parameter_count_per_expert: Optional[float] = None,
) -> float:
    if model is not None and model.architecture == ModelArchitecture.moe:
        active_parameters = _derive_active_parameter_count(model, parameter_count, parameter_count_per_expert)
    else:
        active_parameters = parameter_count
    return active_parameters * weight_bits / BITS_PER_BYTE * eta_pack


def derive_kv_bytes_per_token(
    num_layers: int,
    num_kv_heads: int,
    head_dim: int,
    kv_cache_bytes_per_element: float,
) -> float:
    return KV_CACHE_COPIES * num_layers * num_kv_heads * head_dim * kv_cache_bytes_per_element


def derive_runtime_overhead_bytes(runtime: str, weight_bytes: float, kv_cache_bytes: float) -> float:
    base_bytes = runtime_base_overhead_gib(runtime) * GIB_BYTES
    return base_bytes + RUNTIME_OVERHEAD_FRACTION * (weight_bytes + kv_cache_bytes)


def estimate_vram_footprint(
    *,
    model: Optional[ModelArch] = None,
    parameter_count: float,
    num_layers: int,
    num_kv_heads: int,
    head_dim: int,
    weight_bits: float,
    eta_pack: float = DEFAULT_ETA_PACK,
    kv_cache_bytes_per_element: float,
    context_tokens: int,
    batch_size: int,
    runtime: str,
    vram_capacity_mib: int,
    parameter_count_per_expert: Optional[float] = None,
) -> VramFootprint:
    for name, value in (
        ("parameter_count", parameter_count),
        ("weight_bits", weight_bits),
        ("num_layers", num_layers),
        ("num_kv_heads", num_kv_heads),
        ("head_dim", head_dim),
        ("kv_cache_bytes_per_element", kv_cache_bytes_per_element),
        ("context_tokens", context_tokens),
        ("batch_size", batch_size),
        ("vram_capacity_mib", vram_capacity_mib),
    ):
        _require_positive(name, value)
    weight_bytes = derive_weight_bytes(parameter_count, weight_bits, eta_pack, model, parameter_count_per_expert)
    kv_bytes_per_token = derive_kv_bytes_per_token(num_layers, num_kv_heads, head_dim, kv_cache_bytes_per_element)
    kv_cache_bytes = kv_bytes_per_token * context_tokens * batch_size
    runtime_overhead_bytes = derive_runtime_overhead_bytes(runtime, weight_bytes, kv_cache_bytes)
    peak_vram_bytes = weight_bytes + kv_cache_bytes + runtime_overhead_bytes
    return VramFootprint(
        weight_bytes=weight_bytes,
        kv_bytes_per_token=kv_bytes_per_token,
        kv_cache_bytes=kv_cache_bytes,
        runtime_overhead_bytes=runtime_overhead_bytes,
        peak_vram_bytes=peak_vram_bytes,
        vram_capacity_bytes=vram_capacity_mib * MIB_BYTES,
    )
