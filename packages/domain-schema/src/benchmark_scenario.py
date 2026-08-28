from typing import Literal

from pydantic import BaseModel, Field


class BenchmarkScenario(BaseModel):
    """LLM scenario (0.9.0 contract; constructible as before)."""

    scenario_kind: Literal["llm"] = "llm"
    prompt_tokens: int = Field(ge=0)
    generated_tokens: int = Field(gt=0)
    batch_size: int = Field(gt=0)
    context_tokens: int = Field(gt=0)


class VideoScenario(BaseModel):
    """Video/diffusion scenario (Épico 1).

    Own fields, never the token fields of BenchmarkScenario (AD-1).
    ``scenario_kind`` is required so a video payload can never validate as an
    LLM scenario by accident.
    """

    scenario_kind: Literal["video"]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    frames: int = Field(gt=0)
    steps: int = Field(gt=0)
    cfg: float = Field(gt=0)
    shift: float = Field(default=5.0, ge=0)
    seed: int
