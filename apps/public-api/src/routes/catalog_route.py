"""Public catalog routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from src.dependencies.database_session_provider import DatabaseSession, get_database_session

router = APIRouter(prefix="/v1", tags=["catalog"])

# Pagination is omitted because the complete catalog fits in one response today.
# Limit/offset will be added when it no longer fits.


def _as_float(value: Any) -> float | None:
    return None if value is None else float(value)


@router.get("/model-releases")
def list_model_releases(
    session: DatabaseSession = Depends(get_database_session),
) -> dict[str, Any]:
    items = [
        {
            "id": row["id"],
            "release_name": row["release_name"],
            "family": row["family"],
            "parameter_count_billion": _as_float(row["parameter_count_billion"]),
            "max_context_tokens": row["max_context_tokens"],
        }
        for row in sorted(session.fetch_all_model_releases(), key=lambda item: item["id"])
    ]
    return {"items": items, "count": len(items)}


@router.get("/quantization-profiles")
def list_quantization_profiles(
    session: DatabaseSession = Depends(get_database_session),
) -> dict[str, Any]:
    items = [
        {
            "id": row["id"],
            "display_name": row["display_name"],
            "weight_format": row["weight_format"],
            "weight_bits": _as_float(row["weight_bits"]),
        }
        for row in sorted(session.fetch_quantization_profiles(), key=lambda item: item["id"])
    ]
    return {"items": items, "count": len(items)}
