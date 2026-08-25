"""Artifact vault provider (plan decisions 7 and 12).

Defines the ``ArtifactVault`` interface, a local filesystem implementation for
Phase 0, and the FastAPI dependency that resolves the vault from app state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import Request


class ArtifactVault(ABC):
    """Stores raw benchmark artifact bytes behind a thin interface."""

    @abstractmethod
    def store(self, storage_key: str, data: bytes) -> str:
        """Persist ``data`` under ``storage_key`` and return the storage key."""


class LocalArtifactVault(ArtifactVault):
    """Filesystem-backed vault storing artifacts under a base directory."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = Path(base_dir)

    def store(self, storage_key: str, data: bytes) -> str:
        target = self._base_dir / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return storage_key


def get_artifact_vault(request: Request) -> ArtifactVault:
    """FastAPI dependency resolving the configured artifact vault."""
    return request.app.state.artifact_vault
