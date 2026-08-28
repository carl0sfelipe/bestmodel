"""Roofline diffusion-step prediction (Épico 3, Story 3.1).

Estimates how many seconds one sampling step (and one full clip) of a latent
video diffusion model costs on a given GPU. The model is deliberately
roofline-simple and every coefficient is a named constant with its rationale:

    T            = (W/8) * (H/8) * ((F-1)/4 + 1)        latent tokens
    FLOPs_linear = 2 * N_active * T                     projection/MLP passes
    FLOPs_attn   = 4 * f_attn * L * T^2 * d             effective quadratic attention
    FLOPs_step   = FLOPs_linear + FLOPs_attn
    t_compute    = FLOPs_step / (fp16_tflops * dtype_factor * U_COMPUTE)
    t_memory     = W_bytes / (BW * U_MEMORY)            weight re-read floor
    t_step       = max(t_compute, t_memory)             roofline max
    t_clip       = steps * t_step

``f_attn`` is the one calibration knob: real video DiTs use windowed /
factored attention, so only a fraction of the naive O(T^2) term is actually
paid. Its default is a declared calibration gap — it MUST be re-fit against
the owner's measured 6x3090 cells (Story 1.4) before any derived cell is
published as trustworthy; until then cells carry ``derived`` source class.

All numbers are deterministic; no randomness is used.
"""

from gpu_spec import GpuSpec

U_COMPUTE = 0.5
"""Fraction of nominal dense fp16 TFLOPs a real diffusion step sustains
(kernel launch overhead, non-fused ops, activation traffic)."""

U_MEMORY = 0.8
"""Fraction of nominal memory bandwidth achieved (same spirit as the decode
estimator)."""

ATTENTION_QUADRATIC_FRACTION = 0.05
"""Effective share of the naive O(T^2) attention actually paid after windowed/
factored attention. CALIBRATION GAP: re-fit against Story 1.4 measured cells."""

LATENT_SPATIAL_DIVISOR = 8
LATENT_TEMPORAL_DIVISOR = 4

FP16_COMPUTE_FACTOR = 1.0
FP8_COMPUTE_FACTOR = 2.0
"""fp8 tensor cores double the dense matmul rate — but ONLY on architectures
with native fp8 (sm89+ e.g. RTX 4090, sm90 e.g. H100). Ampere (sm86, e.g. RTX
3090) dequantizes fp8 to fp16 compute, so the factor clamps to 1.0 there."""

_GIB = 1024.0 ** 3


class DiffusionWorkload:
    """Video diffusion workload definition (recipe-shaped)."""

    def __init__(
        self,
        width: int,
        height: int,
        frames: int,
        steps: int,
        active_parameters_billion: float,
        num_layers: int,
        hidden_size: int,
        weight_bits: float = 16.0,
        has_native_fp8: bool = False,
    ) -> None:
        self.width = width
        self.height = height
        self.frames = frames
        self.steps = steps
        self.active_parameters_billion = active_parameters_billion
        self.num_layers = num_layers
        self.hidden_size = hidden_size
        self.weight_bits = weight_bits
        # An fp8 workload only doubles compute where the silicon supports it.
        self.effective_dtype_factor = (
            FP8_COMPUTE_FACTOR if (weight_bits <= 8.0 and has_native_fp8) else FP16_COMPUTE_FACTOR
        )


def derive_latent_tokens(width: int, height: int, frames: int) -> int:
    """Latent token count after the VAE compression (8x spatial, 4x temporal).

    81 frames -> (81-1)/4 + 1 = 21 latent frames; 1280x720 -> 160x90.
    """
    latent_frames = (frames - 1) // LATENT_TEMPORAL_DIVISOR + 1
    return (width // LATENT_SPATIAL_DIVISOR) * (height // LATENT_SPATIAL_DIVISOR) * latent_frames


def derive_step_flops(workload: DiffusionWorkload) -> float:
    """FLOPs for one sampling step: linear passes + effective attention."""
    tokens = derive_latent_tokens(workload.width, workload.height, workload.frames)
    linear_flops = 2.0 * workload.active_parameters_billion * 1e9 * tokens
    attention_flops = (
        4.0
        * ATTENTION_QUADRATIC_FRACTION
        * workload.num_layers
        * float(tokens) ** 2
        * workload.hidden_size
    )
    return linear_flops + attention_flops


def estimate_seconds_per_step(hardware: GpuSpec, workload: DiffusionWorkload) -> float:
    """Roofline max of compute time and the weight-read memory floor."""
    flops = derive_step_flops(workload)
    if hardware.fp16_tflops is None or hardware.fp16_tflops <= 0:
        raise ValueError(f"gpu {hardware.id} has no fp16_tflops spec")
    compute_seconds = flops / (hardware.fp16_tflops * 1e12 * workload.effective_dtype_factor * U_COMPUTE)
    weight_bytes = workload.active_parameters_billion * 1e9 * (workload.weight_bits / 8.0)
    memory_seconds = weight_bytes / (hardware.memory_bandwidth_gib_s * _GIB * U_MEMORY)
    return max(compute_seconds, memory_seconds)


def estimate_seconds_per_clip(hardware: GpuSpec, workload: DiffusionWorkload) -> float:
    """Clip wall time from sampling only. DECLARED EXCLUSION: text-encoder
    prompt evaluation and VAE decode are not modelled (typically small
    relative to sampling, but they are why real clips run slightly longer)."""
    return workload.steps * estimate_seconds_per_step(hardware, workload)
