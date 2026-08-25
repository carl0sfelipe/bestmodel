"""Request models for the auth routes (S13).

Handles are normalized to lowercase at the route boundary; the pattern matches
the ``app_user`` CHECK constraint in migration 0005.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

HANDLE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")


class PasskeyRegisterOptionsRequest(BaseModel):
    handle: str = Field(min_length=2, max_length=32)
    display_name: str | None = Field(default=None, min_length=1, max_length=64)


class PasskeyRegisterVerifyRequest(BaseModel):
    handle: str = Field(min_length=2, max_length=32)
    credential: dict


class PasskeyLoginOptionsRequest(BaseModel):
    handle: str = Field(min_length=2, max_length=32)


class PasskeyLoginVerifyRequest(BaseModel):
    handle: str = Field(min_length=2, max_length=32)
    credential: dict


class AgentTokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
