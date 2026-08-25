from enum import StrEnum

from pydantic import BaseModel, Field


class MetricKind(StrEnum):
    ttft_ms = "ttft_ms"
    prefill_tok_s = "prefill_tok_s"
    decode_tok_s = "decode_tok_s"
    peak_vram_mib = "peak_vram_mib"
    peak_ram_mib = "peak_ram_mib"
    power_watt_avg = "power_watt_avg"
    temperature_c_max = "temperature_c_max"
    energy_joule = "energy_joule"


class BenchmarkMetrics(BaseModel):
    ttft_ms: float = Field(ge=0)
    prefill_tok_s: float = Field(ge=0)
    decode_tok_s: float = Field(ge=0)
    peak_vram_mib: int = Field(gt=0)
    power_watt_avg: float = Field(ge=0)
