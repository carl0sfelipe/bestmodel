"""S27 contract: per-contributor points export on BOTH backends.

Points v0 (frozen in specs/en/S27-contributor-export.md): a validated
signed run is worth 2. Only contributors with >= 1 validated signed run
appear. Postgres leg skips without DATABASE_URL (house pattern — it runs
inside make gate).
"""

from __future__ import annotations

import os
import uuid

import pytest

from fake_database import FakeDatabase


def _pem() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _add_user(db: FakeDatabase, handle: str) -> dict:
    user = {
        "id": str(uuid.uuid4()),
        "handle": handle,
        "created_at": "2026-08-30T00:00:00+00:00",
    }
    db.insert_app_user(user)
    return user


def _add_key(db: FakeDatabase, user_id: str) -> dict:
    key = {
        "id": str(uuid.uuid4()),
        "app_user_id": user_id,
        "label": "rig",
        "public_key_pem": _pem(),
        "algorithm": "ed25519",
        "created_at": "2026-08-30T00:00:00+00:00",
        "revoked_at": None,
    }
    db.insert_signing_key(key)
    return key


def _add_run(db: FakeDatabase, key_id: str, status: str = "validated") -> None:
    db._runs.append(
        {
            "id": str(uuid.uuid4()),
            "status": status,
            "signature_key_id": key_id,
        }
    )


def _assert_contract(rows: list[dict]) -> None:
    assert [r["handle"] for r in rows] == ["ana", "bruno"], rows
    assert rows[0] == {"handle": "ana", "points": 4, "validated_runs": 2}
    assert rows[1] == {"handle": "bruno", "points": 2, "validated_runs": 1}
    for r in rows:
        assert set(r.keys()) == {"handle", "points", "validated_runs"}


def test_fake_contributor_points_derivation():
    db = FakeDatabase()
    ana, bruno = _add_user(db, "ana"), _add_user(db, "bruno")
    key_a, key_b = _add_key(db, ana["id"]), _add_key(db, bruno["id"])
    _add_run(db, key_a["id"])
    _add_run(db, key_a["id"])
    _add_run(db, key_b["id"])
    _add_run(db, key_a["id"], status="failed")  # não-validada NÃO conta
    # sem assinatura: run validada órfã não entra (proveniência é a chave)
    _add_run(db, "", status="validated")
    _assert_contract(db.fetch_contributor_points())


def test_fake_contributor_points_empty_when_no_signed_runs():
    db = FakeDatabase()
    _add_user(db, "nadia")
    assert db.fetch_contributor_points() == []


def test_postgres_contributor_points():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL not set — Postgres leg runs inside make gate")
    import psycopg

    from src.dependencies.database_session_provider import PostgresSession

    try:
        conn = psycopg.connect(dsn, row_factory=dict_row)
    except psycopg.OperationalError as exc:
        pytest.skip(f"DATABASE_URL unreachable ({exc})")
    session = PostgresSession(conn)
    rows = session.fetch_contributor_points()
    for r in rows:
        assert set(r.keys()) == {"handle", "points", "validated_runs"}
        assert r["points"] == r["validated_runs"] * 2
    assert rows == sorted(rows, key=lambda r: (-r["points"], r["handle"]))
