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
    seconds_per_clip = "seconds_per_clip"
    it_per_s = "it_per_s"
    frames_per_s = "frames_per_s"


class BenchmarkMetrics(BaseModel):
    ttft_ms: float = Field(ge=0)
    prefill_tok_s: float = Field(ge=0)
    decode_tok_s: float = Field(ge=0)
    # Video runs may execute on machines without nvidia-smi access, where the
    # CLI reports 0; LLM runs keep reporting a positive peak.
    peak_vram_mib: int = Field(default=0, ge=0)
    power_watt_avg: float = Field(ge=0)
    # Video/diffusion metrics (Épico 1). None on LLM runs; never derived from
    # the tok/s fields above (AD-1).
    seconds_per_clip: float | None = Field(default=None, ge=0)
    it_per_s: float | None = Field(default=None, ge=0)
    frames_per_s: float | None = Field(default=None, ge=0)
