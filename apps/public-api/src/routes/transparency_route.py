"""Transparency route (Story 5.3): public explanation of source classes."""

from __future__ import annotations

from fastapi import APIRouter

from src.services.source_transparency import source_transparency

router = APIRouter(prefix="/v1/transparency", tags=["transparency"])


@router.get("/sources")
def get_source_transparency() -> dict:
    return source_transparency()
