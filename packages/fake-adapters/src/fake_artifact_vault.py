"""In-memory artifact vault used by tests (fake adapter)."""

from __future__ import annotations

from src.dependencies.artifact_vault_provider import ArtifactVault


class FakeArtifactVault(ArtifactVault):
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def store(self, storage_key: str, data: bytes) -> str:
        self._objects[storage_key] = bytes(data)
        return storage_key

    def retrieve(self, storage_key: str) -> bytes | None:
        return self._objects.get(storage_key)
