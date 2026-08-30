"""S28 contract: run reports (denúncia de run irreal) on BOTH backends.

Frozen in specs/en/S28-run-report-and-provenance.md:
- report never touches the target; confirm is a moderator act;
- confirm awards the reporter (+5, awarded_at) and refutes the claim;
- dismiss has no effect on the target;
- moderation = handle in MODERATOR_HANDLES;
- points = validated_runs*2 + confirmed awarded reports*5 (lockstep with
  fetch_contributor_points — S27 contract extended, never weakened).
Postgres leg skips without DATABASE_URL (house pattern — it runs inside
make gate).
"""

from __future__ import annotations

import os
import uuid

import pytest

from fake_database import FakeDatabase


def _add_user(db: FakeDatabase, handle: str) -> dict:
    user = {
        "id": str(uuid.uuid4()),
        "handle": handle,
        "created_at": "2026-08-30T00:00:00+00:00",
    }
    db.insert_app_user(user)
    return user


def _add_claim(db: FakeDatabase, model_id: str = "model-test") -> dict:
    claim = {
        "id": str(uuid.uuid4()),
        "claimant_id": None,
        "source": "localmaxxing",
        "external_ref": f"localmaxxing:rig:{model_id}:{uuid.uuid4().hex[:6]}",
        "model_release_id": model_id,
        "claimed_metrics": {"decode_tok_s": 10.0},
        "prior_snapshot": {},
        "status": "open",
        "created_at": "2026-08-30T00:00:00+00:00",
        "updated_at": "2026-08-30T00:00:00+00:00",
    }
    db.insert_run_claim(claim)
    return claim


def _report_payload(category: str = "numbers_unreal") -> dict:
    return {"reason_category": category, "reason_detail": "irreal"}


def _service():
    from src.services.create_run_report import create_run_report

    return create_run_report


def test_fake_report_confirm_awards_and_refutes():
    db = FakeDatabase()
    reporter = _add_user(db, "denunciante")
    claim = _add_claim(db)

    create = _service()
    view = create(db, reporter, "run_claim", claim["id"], _report_payload())
    assert view["status"] == "open"
    # a denúncia NUNCA altera o alvo
    assert db.find_run_claim_by_id(claim["id"])["status"] == "open"
    # duplicada em aberto reprova
    from src.services.auth_common import AuthError

    with pytest.raises(AuthError) as exc:
        create(db, reporter, "run_claim", claim["id"], _report_payload())
    assert exc.value.status_code == 409

    # moderação: handle fora da lista é 403
    moderator = _add_user(db, "moderador")
    os.environ["MODERATOR_HANDLES"] = "moderador"
    try:
        from src.services.create_run_report import confirm_report, dismiss_report

        outsider = _add_user(db, "espezim")
        with pytest.raises(AuthError) as exc:
            confirm_report(db, outsider, view["id"])
        assert exc.value.status_code == 403

        result = confirm_report(db, moderator, view["id"])
        assert result == {"id": view["id"], "status": "confirmed", "awarded": True}
        # mecânica fake pego: claim refutada + report confirmed com awarded_at
        assert db.find_run_claim_by_id(claim["id"])["status"] == "refuted"
        report = db.find_run_report_by_id(view["id"])
        assert report["status"] == "confirmed" and report["awarded_at"]
        # confirmar duas vezes reprova
        with pytest.raises(AuthError):
            confirm_report(db, moderator, view["id"])

        # pontos: denunciante tem 0 runs mas 1 denúncia confirmada = +5
        points = {r["handle"]: r for r in db.fetch_contributor_points()}
        assert points["denunciante"] == {"handle": "denunciante", "points": 5, "validated_runs": 0}
        assert "moderador" not in points

        # dismiss: sem efeito no alvo
        other = _add_claim(db)
        v2 = create(db, reporter, "run_claim", other["id"], _report_payload("wrong_model"))
        dismissed = dismiss_report(db, moderator, v2["id"])
        assert dismissed == {"id": v2["id"], "status": "dismissed"}
        assert db.find_run_claim_by_id(other["id"])["status"] == "open"
    finally:
        os.environ.pop("MODERATOR_HANDLES", None)


def test_fake_report_requires_existing_target_and_valid_category():
    db = FakeDatabase()
    reporter = _add_user(db, "rep")
    claim = _add_claim(db)
    create = _service()
    from src.services.auth_common import AuthError

    with pytest.raises(AuthError) as exc:
        create(db, reporter, "run_claim", str(uuid.uuid4()), _report_payload())
    assert exc.value.status_code == 404
    with pytest.raises(AuthError) as exc:
        create(db, reporter, "run_claim", claim["id"], {"reason_category": "achei-que-nao"})
    assert exc.value.status_code == 400
    # categoria válida em alvo real passa das checagens de payload (denúncia criada)
    view = create(db, reporter, "run_claim", claim["id"], _report_payload())
    assert view["status"] == "open"


def test_fake_report_rate_limit():
    db = FakeDatabase()
    reporter = _add_user(db, "impetuoso")
    targets = [_add_claim(db) for _ in range(11)]
    create = _service()
    from src.services.auth_common import AuthError

    for claim in targets[:10]:
        create(db, reporter, "run_claim", claim["id"], _report_payload())
    with pytest.raises(AuthError) as exc:
        create(db, reporter, "run_claim", targets[10]["id"], _report_payload())
    assert exc.value.status_code == 429


def test_fake_report_points_lockstep_with_runs():
    """S27 estendido: runs validadas ×2 + denúncia confirmada ×5, na mesma linha."""
    db = FakeDatabase()
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    signer = _add_user(db, "multi")
    key = {
        "id": str(uuid.uuid4()),
        "app_user_id": signer["id"],
        "label": "rig",
        "public_key_pem": Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8"),
        "algorithm": "ed25519",
        "created_at": "2026-08-30T00:00:00+00:00",
        "revoked_at": None,
    }
    db.insert_signing_key(key)
    db._runs.append({"id": str(uuid.uuid4()), "status": "validated", "signature_key_id": key["id"]})

    claim = _add_claim(db)
    reporter = _add_user(db, "vigilante")
    _service()(db, reporter, "run_claim", claim["id"], _report_payload())
    os.environ["MODERATOR_HANDLES"] = "m"
    try:
        moderator = _add_user(db, "m")
        from src.services.create_run_report import confirm_report

        report_id = db.find_open_run_report(reporter["id"], "run_claim", claim["id"])["id"]
        confirm_report(db, moderator, report_id)
    finally:
        os.environ.pop("MODERATOR_HANDLES", None)

    rows = {r["handle"]: r for r in db.fetch_contributor_points()}
    assert rows["multi"] == {"handle": "multi", "points": 2, "validated_runs": 1}
    assert rows["vigilante"] == {"handle": "vigilante", "points": 5, "validated_runs": 0}
    assert rows["multi"]["points"] > 0 and rows["vigilante"]["points"] > 0
    assert [r["handle"] for r in sorted(rows.values(), key=lambda r: -r["points"])][:2]


def test_postgres_run_reports():
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
    # a migração 0014 tem de existir no banco alvo
    cols = session._fetchall(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'run_claim' AND column_name = 'provenance'",
        (),
    )
    assert cols, "migration 0014 (run_claim.provenance) não aplicada"
    reports = session.list_run_reports(None, 5)
    assert isinstance(reports, list)
    conn.close()
