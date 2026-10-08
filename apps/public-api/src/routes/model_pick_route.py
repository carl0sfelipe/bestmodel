"""Model pick route (S49): best model per intent and VRAM."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.services.model_pick import PickError, pick_models

router = APIRouter(prefix="/v1", tags=["pick"])


@router.get("/pick")
def get_model_pick(
    intent: str,
    vram_gib: float = Query(gt=0),
    gpu: str = Query(min_length=1),
    limit: int | None = Query(default=None, ge=1, le=20),
) -> dict:
    try:
        return pick_models(intent, vram_gib, gpu, limit)
    except PickError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
