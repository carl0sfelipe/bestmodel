from datetime import date

from pydantic import BaseModel, Field


class GpuSpec(BaseModel):
    id: str
    vendor: str
    marketing_name: str
    vram_mib: int = Field(gt=0)
    memory_bandwidth_gib_s: float = Field(gt=0)
    fp16_tflops: float | None = None
    int8_tops: float | None = None
    tdp_watt: int = Field(gt=0)
    pcie_generation: int | None = None
    pcie_lane_width: int | None = None
    supports_nvlink: bool = False
    released_at: date | None = None
