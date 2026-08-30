"""S25a contract inventory: every DatabaseSession method on every backend.

Introspects the ABC so a ported interface without bodies (the U4 failure
class: interface copied, seven implementations missing) fails HERE, at test
time, naming the missing methods — no database needed. The PostgresSession
instantiation smoke catches unimplemented abstractmethods by construction
(TypeError on instantiation).
"""

from __future__ import annotations

import pytest

from fake_database import FakeDatabase
from src.dependencies.database_session_provider import DatabaseSession, PostgresSession

BACKENDS = [FakeDatabase, PostgresSession]


@pytest.mark.parametrize("backend", BACKENDS, ids=["fake", "postgres"])
def test_backend_implements_every_abc_method(backend: type) -> None:
    missing = set(DatabaseSession.__abstractmethods__) - set(dir(backend))
    assert not missing, (
        f"{backend.__name__} is missing DatabaseSession methods: {sorted(missing)}"
    )


@pytest.mark.parametrize("backend", BACKENDS, ids=["fake", "postgres"])
def test_backend_is_instantiable_session_subclass(backend: type) -> None:
    assert issubclass(backend, DatabaseSession)
    # PostgresSession(None) is safe: the connection is only stored, never used;
    # instantiation itself is the smoke — an unimplemented abstractmethod
    # raises TypeError here. No close(): there is no real connection.
    instance = FakeDatabase() if backend is FakeDatabase else backend(None)
    assert isinstance(instance, DatabaseSession)
