"""Request models for rig routes (S14)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateRigRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{2,62}$")
    topology: dict = Field(default_factory=dict)
    is_public: bool = True


class UpdateRigRequest(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    topology: dict | None = None
    is_public: bool | None = None


class BindRigRequest(BaseModel):
    hardware_submission_id: str = Field(min_length=1, max_length=64)
