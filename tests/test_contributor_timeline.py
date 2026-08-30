"""E6-4.5 contract: contributor timeline (account_created_at +
first_signed_run_at) on BOTH backends.

ADDITIVE to the frozen S27 export: travels as a separate top-level
'timeline' key consumed by the Lineup's referral-conversion window dial.
The frozen contributors rows (handle/points/validated_runs) are untouched.
"""

from __future__ import annotations

import os
import uuid

import pytest

from fake_database import FakeDatabase


def _add_user(db: FakeDatabase, handle: str, created_at: str) -> dict:
    user = {
        "id": str(uuid.uuid4()),
        "handle": handle,
        "created_at": created_at,
    }
    db.insert_app_user(user)
    return user


def _add_key(db: FakeDatabase, user_id: str) -> dict:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = {
        "id": str(uuid.uuid4()),
        "app_user_id": user_id,
        "label": "rig",
        "public_key_pem": Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8"),
        "algorithm": "ed25519",
        "created_at": "2026-08-01T00:00:00+00:00",
        "revoked_at": None,
    }
    db.insert_signing_key(key)
    return key


def test_fake_timeline_derivation():
    db = FakeDatabase()
    ana = _add_user(db, "ana", "2026-08-01T00:00:00+00:00")
    bruno = _add_user(db, "bruno", "2026-08-20T00:00:00+00:00")
    key_a = _add_key(db, ana["id"])
    _add_key(db, bruno["id"])  # chave sem run nenhuma
    # 2 runs assinadas validadas de ana: a 1ª define first_signed_run_at
    db._runs.append({"id": str(uuid.uuid4()), "status": "validated",
                     "signature_key_id": key_a["id"], "submitted_at": "2026-08-05T12:00:00+00:00"})
    db._runs.append({"id": str(uuid.uuid4()), "status": "validated",
                     "signature_key_id": key_a["id"], "submitted_at": "2026-08-03T12:00:00+00:00"})
    # run falhada NÃO conta como first signed run
    db._runs.append({"id": str(uuid.uuid4()), "status": "failed",
                     "signature_key_id": key_a["id"], "submitted_at": "2026-08-02T12:00:00+00:00"})

    tl = {t["handle"]: t for t in db.fetch_contributor_timeline()}
    assert tl["ana"] == {
        "handle": "ana",
        "account_created_at": "2026-08-01T00:00:00+00:00",
        "first_signed_run_at": "2026-08-03T12:00:00+00:00",
    }
    # usuário com chave mas sem run: account existe, first run não
    assert tl["bruno"]["first_signed_run_at"] is None
    assert tl["bruno"]["account_created_at"] == "2026-08-20T00:00:00+00:00"


def test_postgres_timeline():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL not set — Postgres leg runs inside make gate")
    import psycopg
    from psycopg.rows import dict_row

    from src.dependencies.database_session_provider import PostgresSession

    try:
        conn = psycopg.connect(dsn, row_factory=dict_row)
    except psycopg.OperationalError as exc:
        pytest.skip(f"DATABASE_URL unreachable ({exc})")
    session = PostgresSession(conn)
    rows = session.fetch_contributor_timeline()
    for r in rows:
        assert set(r.keys()) == {"handle", "account_created_at", "first_signed_run_at"}
    conn.close()
