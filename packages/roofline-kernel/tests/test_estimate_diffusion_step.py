"""Tests for the diffusion-step roofline estimator (Story 3.1).

Deterministic hand-computed checks plus the cross-GPU ratio expectation from
the spec sheet; the calibration knob (ATTENTION_QUADRATIC_FRACTION) is pinned
by the exact hand-computed cases and must be re-fit against measured cells.
"""

import pytest

from estimate_diffusion_step import (
    ATTENTION_QUADRATIC_FRACTION,
    FP8_COMPUTE_FACTOR,
    U_COMPUTE,
    DiffusionWorkload,
    derive_latent_tokens,
    derive_step_flops,
    estimate_seconds_per_clip,
    estimate_seconds_per_step,
)
from hardware_fixtures import RTX_3090, RTX_4090

WAN22_FLF2V_720P = DiffusionWorkload(
    width=1280,
    height=720,
    frames=81,
    steps=20,
    active_parameters_billion=14.0,
    num_layers=40,
    hidden_size=5120,
    weight_bits=16.0,
    has_native_fp8=False,
)


def test_latent_tokens_match_hand_computation():
    # 1280/8 * 720/8 * ((81-1)/4 + 1) = 160 * 90 * 21 = 302400
    assert derive_latent_tokens(1280, 720, 81) == 160 * 90 * 21
    assert derive_latent_tokens(1280, 720, 81) == 302400
    # Smoke scenario 320x320/25f: 40 * 40 * 7 = 11200 tokens
    assert derive_latent_tokens(320, 320, 25) == 40 * 40 * 7


def test_step_flops_match_hand_computation():
    workload = DiffusionWorkload(
        width=320,
        height=320,
        frames=25,
        steps=4,
        active_parameters_billion=1.0,
        num_layers=2,
        hidden_size=64,
    )
    tokens = 11200.0
    linear = 2.0 * 1e9 * tokens
    attention = 4.0 * ATTENTION_QUADRATIC_FRACTION * 2 * tokens**2 * 64
    expected = linear + attention
    assert derive_step_flops(workload) == pytest.approx(expected, rel=1e-12)


def test_seconds_per_step_matches_hand_computation():
    flops = derive_step_flops(WAN22_FLF2V_720P)
    expected = flops / (RTX_3090.fp16_tflops * 1e12 * 1.0 * U_COMPUTE)
    assert estimate_seconds_per_step(RTX_3090, WAN22_FLF2V_720P) == pytest.approx(expected, rel=1e-12)


def test_rtx3090_vs_rtx4090_ratio_in_spec_expected_range():
    """Same fp16 workload: ratio must track the spec-sheet compute ratio
    (165/35.6 = 4.63x) inside a tolerance band, not flip sign or explode."""
    fp16_4090 = DiffusionWorkload(
        width=1280, height=720, frames=81, steps=20,
        active_parameters_billion=14.0, num_layers=40, hidden_size=5120,
        weight_bits=16.0, has_native_fp8=False,
    )
    per_step_3090 = estimate_seconds_per_step(RTX_3090, fp16_4090)
    per_step_4090 = estimate_seconds_per_step(RTX_4090, fp16_4090)
    ratio = per_step_3090 / per_step_4090
    assert 3.0 <= ratio <= 5.5, f"ratio {ratio:.2f} outside spec-expected band"
    assert ratio == pytest.approx(165.0 / 35.6, rel=1e-9)


def test_fp8_doubles_compute_only_with_native_support():
    fp8_native = DiffusionWorkload(
        width=1280, height=720, frames=81, steps=20,
        active_parameters_billion=14.0, num_layers=40, hidden_size=5120,
        weight_bits=8.0, has_native_fp8=True,
    )
    fp8_ampere = DiffusionWorkload(
        width=1280, height=720, frames=81, steps=20,
        active_parameters_billion=14.0, num_layers=40, hidden_size=5120,
        weight_bits=8.0, has_native_fp8=False,
    )
    assert fp8_native.effective_dtype_factor == FP8_COMPUTE_FACTOR
    assert fp8_ampere.effective_dtype_factor == 1.0
    # On the 4090 (sm89) fp8 is 2x faster than fp16...
    assert estimate_seconds_per_step(RTX_4090, fp8_native) == pytest.approx(
        estimate_seconds_per_step(RTX_4090, WAN22_FLF2V_720P) / 2.0, rel=1e-9
    )
    # ...but on the 3090 (sm86, no native fp8) fp8 weights compute at fp16 rate.
    assert estimate_seconds_per_step(RTX_3090, fp8_ampere) == pytest.approx(
        estimate_seconds_per_step(RTX_3090, WAN22_FLF2V_720P), rel=1e-9
    )


def test_clip_time_plausibility_band_720p():
    """720p/81f/20 steps fp16 on one 3090 must land in the multi-hour band the
    community reports for 14B video models (2h..8h); the 4090 with fp8 in the
    tens-of-minutes band (15..60 min)."""
    clip_3090 = estimate_seconds_per_clip(RTX_3090, WAN22_FLF2V_720P)
    assert 2 * 3600 <= clip_3090 <= 8 * 3600, f"3090 fp16 clip {clip_3090/3600:.2f}h out of band"
    fp8_4090 = DiffusionWorkload(
        width=1280, height=720, frames=81, steps=20,
        active_parameters_billion=14.0, num_layers=40, hidden_size=5120,
        weight_bits=8.0, has_native_fp8=True,
    )
    clip_4090 = estimate_seconds_per_clip(RTX_4090, fp8_4090)
    assert 15 * 60 <= clip_4090 <= 60 * 60, f"4090 fp8 clip {clip_4090/60:.1f}min out of band"


def test_clip_time_scales_linearly_with_steps():
    small = DiffusionWorkload(
        width=320, height=320, frames=25, steps=4,
        active_parameters_billion=1.0, num_layers=2, hidden_size=64,
    )
    bigger = DiffusionWorkload(
        width=320, height=320, frames=25, steps=8,
        active_parameters_billion=1.0, num_layers=2, hidden_size=64,
    )
    assert estimate_seconds_per_clip(RTX_3090, bigger) == pytest.approx(
        2.0 * estimate_seconds_per_clip(RTX_3090, small), rel=1e-9
    )


def test_gpu_without_fp16_spec_is_rejected():
    from gpu_spec import GpuSpec

    malformed = GpuSpec(
        id="mystery", vendor="nvidia", marketing_name="?",
        vram_mib=8192, memory_bandwidth_gib_s=300.0, fp16_tflops=None, tdp_watt=100,
    )
    with pytest.raises(ValueError):
        estimate_seconds_per_step(malformed, WAN22_FLF2V_720P)
