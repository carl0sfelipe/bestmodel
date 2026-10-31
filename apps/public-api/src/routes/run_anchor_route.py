"""Run anchor route (EaaS B1): Bitcoin-anchored evidence per validated run.

`GET /v1/runs/{run_id}/anchor` returns the digest that was registered in the
EaaS engine and the `record_id` that resolves the Merkle inclusion proof and
the btc txid at the engine's verify-api (`{EAAS_VERIFY_URL}/v1/records/{id}`).
404 when the run was never anchored (anchoring is opt-in via EAAS_API_KEY on
the intake worker).
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from src.dependencies.database_session_provider import (
    DatabaseSession,
    get_database_session,
)

router = APIRouter(prefix="/v1/runs", tags=["anchor"])


@router.get("/{run_id}/anchor")
def get_run_anchor(
    run_id: str,
    session: DatabaseSession = Depends(get_database_session),
) -> JSONResponse:
    anchor = session.fetch_run_anchor(run_id)
    if anchor is None:
        raise HTTPException(status_code=404, detail="run without anchor")
    verify_base = os.environ.get("EAAS_VERIFY_URL", "https://verify.provably.click").rstrip("/")
    return JSONResponse(
        {
            "run_id": anchor["run_id"],
            "digest": anchor["digest"],
            "record_id": anchor["record_id"],
            "studio_id": anchor["studio_id"],
            "anchored_at": anchor["anchored_at"],
            "proof_url": f"{verify_base}/v1/records/{anchor['record_id']}",
        }
    )
