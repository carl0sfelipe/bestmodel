"""Request models for run-claim routes (S15)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateRunClaimRequest(BaseModel):
    model_release_id: str = Field(min_length=1, max_length=128)
    claimed_metrics: dict = Field(min_length=1)
    rig_slug: str | None = Field(default=None, min_length=3, max_length=63)
    quantization_profile_id: str | None = Field(default=None, max_length=64)
    inference_runtime_id: str | None = Field(default=None, max_length=64)
    gpu_model_id: str | None = Field(default=None, max_length=64)
    context_tokens: int | None = Field(default=None, gt=0, le=10_000_000)
    note: str | None = Field(default=None, max_length=2000)
    # S29 (rede de captura): o post original (reddit/twitter/github/blog)
    # onde o run foi achado. Null = run presenciado pelo próprio contribuidor.
    source_url: str | None = Field(
        default=None, max_length=500, pattern=r"^https?://\S+$"
    )


class ClaimVoteRequest(BaseModel):
    verdict: str = Field(pattern=r"^(plausible|impossible)$")


CLAIM_SORTS = ("recent", "controversial", "strongest")
