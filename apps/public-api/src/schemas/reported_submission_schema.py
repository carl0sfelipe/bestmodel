"""Pydantic models for the `reported` submission endpoint (Story 5.2).

This is the community path for numbers measured OUTSIDE the signed probe:
authenticated with a lightweight contributor token, quota-limited per source
IP, and stored with ``source_class='reported'`` and ``status='submitted'`` —
the leaderboard only ever shows validated rows, so a reported cell is visible
solely after human review (FR-7).

The scenario is the same domain union the signed intake accepts (LLM token
counts or video dimensions); metrics reuse the report metric names so both
paths land in the same columns/rows.
"""

from pydantic import BaseModel, ConfigDict, Field


class ReportedMetrics(BaseModel):
    """At least one metric must be set; every value is non-negative."""

    model_config = ConfigDict(extra="forbid")

    ttft_ms: float | None = Field(default=None, ge=0)
    prefill_tok_s: float | None = Field(default=None, ge=0)
    decode_tok_s: float | None = Field(default=None, ge=0)
    peak_vram_mib: float | None = Field(default=None, ge=0)
    power_watt_avg: float | None = Field(default=None, ge=0)
    seconds_per_clip: float | None = Field(default=None, ge=0)
    it_per_s: float | None = Field(default=None, ge=0)
    frames_per_s: float | None = Field(default=None, ge=0)


class ReportedSubmissionBody(BaseModel):
    model_release_id: str
    inference_runtime_id: str
    quantization_profile_id: str | None = None
    gpu_model_id: str | None = None
    recipe_id: str | None = None
    source_url: str | None = None
    note: str | None = None
    scenario: dict
    metrics: ReportedMetrics


class ContributorRegistration(BaseModel):
    email: str
