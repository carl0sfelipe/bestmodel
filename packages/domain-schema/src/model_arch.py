from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class ModelArchitecture(StrEnum):
    dense = "dense"
    moe = "moe"
    multimodal = "multimodal"


class ModelArch(BaseModel):
    id: str
    family: str
    release_name: str
    architecture: ModelArchitecture
    parameter_count_billion: float
    active_parameter_count_billion: float | None = None
    num_layers: int = Field(gt=0)
    hidden_size: int = Field(gt=0)
    num_attention_heads: int = Field(gt=0)
    num_kv_heads: int = Field(gt=0)
    head_dim: int = Field(gt=0)
    expert_count: int | None = None
    experts_per_token: int | None = None
    max_context_tokens: int = Field(gt=0)
    released_at: date | None = None
