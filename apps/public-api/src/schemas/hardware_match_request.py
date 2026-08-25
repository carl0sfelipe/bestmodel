"""Pydantic v2 request model for POST /v1/match/hardware-to-models.

Field names match the plan section 9.4 contract verbatim.
"""

from pydantic import BaseModel, Field


class HardwareMatchRequest(BaseModel):
    gpu_model_ids: list[str]
    gpu_count: int = Field(gt=0)
    ram_gib: int = Field(gt=0)
    os_name: str
    target_model_family: str
    target_context_tokens: int = Field(gt=0)
    priority: str = "balanced"
