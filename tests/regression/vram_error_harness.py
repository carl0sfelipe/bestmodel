"""VRAM prediction error harness (Phase 0 exit criterion: P50 error < 10%).

Regression corpus of measured (hardware, model, quantization, scenario) cases
with their observed peak VRAM. Predictions come from the roofline kernel's
estimate_vram_footprint; the harness reports the relative error per case and
the P50 (median) across the corpus.
"""

from __future__ import annotations

import sys
from pathlib import Path
from statistics import median

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _entry in (
    _REPO_ROOT / "packages" / "domain-schema" / "src",
    _REPO_ROOT / "packages" / "roofline-kernel" / "src",
):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from roofline_kernel import estimate_vram_footprint  # noqa: E402

P50_TARGET_PERCENT = 10.0

# Measured on the rented RTX 3090 lab machine (llm_lab_export, 2026-08-02):
# QwQ-32B Q4_K_M, llama.cpp CUDA, full GPU offload, nvidia-smi at run end.
# MoE full-offload residency is outside the section 11.2 active-weights model
# and is deliberately excluded from this corpus (tracked for contract 0.9.1).
CORPUS = [
    {
        "name": "RTX 3090 / QwQ-32B Q4_K_M / ctx 4096",
        "parameter_count": 32.8e9,
        "num_layers": 64,
        "num_kv_heads": 8,
        "head_dim": 128,
        "weight_bits": 4.5,
        "context_tokens": 4096,
        "batch_size": 1,
        "vram_capacity_mib": 24576,
        "measured_peak_mib": 20046.0,
    },
    {
        "name": "RTX 3090 / QwQ-32B Q4_K_M / ctx 8192",
        "parameter_count": 32.8e9,
        "num_layers": 64,
        "num_kv_heads": 8,
        "head_dim": 128,
        "weight_bits": 4.5,
        "context_tokens": 8192,
        "batch_size": 1,
        "vram_capacity_mib": 24576,
        "measured_peak_mib": 21074.0,
    },
]


def predict_peak_mib(case: dict) -> float:
    footprint = estimate_vram_footprint(
        parameter_count=case["parameter_count"],
        num_layers=case["num_layers"],
        num_kv_heads=case["num_kv_heads"],
        head_dim=case["head_dim"],
        weight_bits=case["weight_bits"],
        kv_cache_bytes_per_element=2.0,
        context_tokens=case["context_tokens"],
        batch_size=case["batch_size"],
        runtime="llama_cpp",
        vram_capacity_mib=case["vram_capacity_mib"],
    )
    return footprint.peak_vram_bytes / 1048576.0


def relative_error_percent(case: dict) -> float:
    predicted = predict_peak_mib(case)
    return abs(predicted - case["measured_peak_mib"]) / case["measured_peak_mib"] * 100.0


def p50_error_percent() -> float:
    return median(relative_error_percent(case) for case in CORPUS)


def main() -> int:
    print("VRAM prediction error harness (Phase 0 exit criterion: P50 < 10%)")
    for case in CORPUS:
        predicted = predict_peak_mib(case)
        error = relative_error_percent(case)
        print(
            f"  {case['name']}: predicted {predicted:.0f} MiB, "
            f"measured {case['measured_peak_mib']:.0f} MiB, error {error:.2f}%"
        )
    p50 = p50_error_percent()
    print(f"P50 error: {p50:.2f}% (target < {P50_TARGET_PERCENT}%)")
    return 0 if p50 < P50_TARGET_PERCENT else 1


if __name__ == "__main__":
    raise SystemExit(main())
