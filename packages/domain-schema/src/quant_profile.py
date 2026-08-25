from enum import StrEnum

from pydantic import BaseModel, Field


class QuantFormat(StrEnum):
    fp16 = "fp16"
    bf16 = "bf16"
    fp8 = "fp8"
    int8 = "int8"
    int4 = "int4"
    awq = "awq"
    gptq = "gptq"
    exl2 = "exl2"
    gguf_q2 = "gguf_q2"
    gguf_q3 = "gguf_q3"
    gguf_q4 = "gguf_q4"
    gguf_q5 = "gguf_q5"
    gguf_q6 = "gguf_q6"
    gguf_q8 = "gguf_q8"


class KvCacheFormat(StrEnum):
    fp16 = "fp16"
    bf16 = "bf16"
    fp8 = "fp8"
    int8 = "int8"
    int4 = "int4"


class QuantProfile(BaseModel):
    id: str
    display_name: str
    weight_format: QuantFormat
    weight_bits: float = Field(ge=2, le=16)
    kv_cache_format: KvCacheFormat = KvCacheFormat.fp16
    kv_cache_bits: float = Field(ge=4, le=16)
    group_size: int | None = None
    calibration_set: str | None = None
    expected_quality_retention: float | None = Field(default=None, ge=0, le=1)
