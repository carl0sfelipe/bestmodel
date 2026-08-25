from pydantic import BaseModel, Field


class CpuSpec(BaseModel):
    id: str
    vendor: str
    marketing_name: str
    physical_cores: int = Field(gt=0)
    threads: int = Field(gt=0)
    memory_channels: int = Field(gt=0)
    theoretical_memory_bandwidth_gib_s: float | None = None
    tdp_watt: int | None = None
