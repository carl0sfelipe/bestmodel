"""Context limit estimation kernel (plan section 11.7).

Computes the maximum context the model fits in VRAM and, when the target
context is unreachable, returns actionable suggestions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from model_arch import ModelArch

from roofline_kernel.estimate_vram_footprint import (
    MIB_BYTES,
    SAFETY_MARGIN,
    _require_positive,
    derive_kv_bytes_per_token,
    derive_runtime_overhead_bytes,
    derive_weight_bytes,
)


@dataclass(frozen=True)
class ContextEstimate:
    max_context_tokens: int
    target_context_tokens: int
    is_feasible: bool
    suggestions: tuple[str, ...]


def estimate_max_context_tokens(
    vram_capacity_mib: int,
    weight_bytes: float,
    runtime_overhead_bytes: float,
    kv_bytes_per_token: float,
    batch_size: int,
    model_max_context_tokens: int,
) -> int:
    _require_positive("vram_capacity_mib", vram_capacity_mib)
    _require_positive("batch_size", batch_size)
    _require_positive("model_max_context_tokens", model_max_context_tokens)
    available_bytes = vram_capacity_mib * MIB_BYTES * SAFETY_MARGIN - weight_bytes - runtime_overhead_bytes
    raw_max_tokens = int(available_bytes // (kv_bytes_per_token * batch_size))
    return max(0, min(raw_max_tokens, model_max_context_tokens))


def _build_suggestions(max_context_tokens: int, target_context_tokens: int) -> tuple[str, ...]:
    return (
        f"maximum acceptable context is {max_context_tokens} tokens (target {target_context_tokens})",
        "consider KV cache quantization (e.g. fp8/int4) to reduce the KV footprint",
        "consider a lower weight quantization to reduce the weight footprint",
        "consider CPU offload of weights to free VRAM",
        "consider hardware with a larger VRAM capacity",
    )


def estimate_context_limit(
    *,
    model: ModelArch,
    parameter_count: float,
    num_layers: int,
    num_kv_heads: int,
    head_dim: int,
    weight_bits: float,
    eta_pack: float,
    kv_cache_bytes_per_element: float,
    target_context_tokens: int,
    batch_size: int,
    runtime: str,
    vram_capacity_mib: int,
    parameter_count_per_expert: Optional[float] = None,
) -> ContextEstimate:
    _require_positive("target_context_tokens", target_context_tokens)
    weight_bytes = derive_weight_bytes(parameter_count, weight_bits, eta_pack, model, parameter_count_per_expert)
    kv_bytes_per_token = derive_kv_bytes_per_token(num_layers, num_kv_heads, head_dim, kv_cache_bytes_per_element)
    kv_at_target = kv_bytes_per_token * target_context_tokens * batch_size
    runtime_overhead_bytes = derive_runtime_overhead_bytes(runtime, weight_bytes, kv_at_target)
    max_context_tokens = estimate_max_context_tokens(
        vram_capacity_mib=vram_capacity_mib,
        weight_bytes=weight_bytes,
        runtime_overhead_bytes=runtime_overhead_bytes,
        kv_bytes_per_token=kv_bytes_per_token,
        batch_size=batch_size,
        model_max_context_tokens=model.max_context_tokens,
    )
    is_feasible = max_context_tokens >= target_context_tokens
    suggestions = _build_suggestions(max_context_tokens, target_context_tokens) if not is_feasible else ()
    return ContextEstimate(
        max_context_tokens=max_context_tokens,
        target_context_tokens=target_context_tokens,
        is_feasible=is_feasible,
        suggestions=suggestions,
    )
