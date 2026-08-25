"""Pydantic v2 request model for POST /v1/match/model-to-hardware."""

from pydantic import BaseModel, Field


class ModelMatchRequest(BaseModel):
    model_release_id: str
    target_context_tokens: int = Field(gt=0)
    batch_size: int = Field(gt=0)
    priority: str = "balanced"
