"""Known-good hardware fixtures for roofline-kernel tests.

Each fixture carries the hardware's nominal memory bandwidth (GB/s marketing
value stored in the ``memory_bandwidth_gib_s`` field) and nominal fp16 compute
(TFLOPs), used as the input to the roofline predictions.
"""

from gpu_spec import GpuSpec

A100_80GB = GpuSpec(
    id="a100-80gb",
    vendor="nvidia",
    marketing_name="A100 80GB",
    vram_mib=81920,
    memory_bandwidth_gib_s=2039.0,
    fp16_tflops=312.0,
    int8_tops=624.0,
    tdp_watt=400,
    supports_nvlink=True,
)

H100_80GB = GpuSpec(
    id="h100-80gb",
    vendor="nvidia",
    marketing_name="H100 80GB",
    vram_mib=81920,
    memory_bandwidth_gib_s=3350.0,
    fp16_tflops=989.0,
    int8_tops=1979.0,
    tdp_watt=700,
    supports_nvlink=True,
)

RTX_4090 = GpuSpec(
    id="rtx-4090",
    vendor="nvidia",
    marketing_name="RTX 4090",
    vram_mib=24576,
    memory_bandwidth_gib_s=1008.0,
    fp16_tflops=165.0,
    int8_tops=330.0,
    tdp_watt=450,
)
