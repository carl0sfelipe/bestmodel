"""GET /v1/health — what is running, verifiable (H12, direction v3).

Returns the git sha and build time baked into the image
(`infra/docker/api.Dockerfile` build args). No dependency probing here:
the container HEALTHCHECK already covers liveness; this answers "which
commit is in prod" without anyone having to remember.
"""

from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "git_sha": os.environ.get("BESTMODEL_GIT_SHA", "unknown"),
        "built_at": os.environ.get("BESTMODEL_BUILT_AT", "unknown"),
        "service": "public-api",
    }
