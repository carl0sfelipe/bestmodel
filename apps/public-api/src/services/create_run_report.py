"""Run reports (S28) — denúncia de run/claim irreal + mecânica "fake pego".

Regras congeladas na spec S28:
- denúncia NUNCA altera o alvo por si só; confirmar é ato de moderação;
- reporter identificado é obrigatório (a mecânica de pontos exige
  identidade); anônimo não pontua;
- confirmar = +5 pontos ao denunciante (awarded_at) e claim vai para
  `refuted` (status que já existia na S15);
- teto de taxa segue o padrão S20 (janela deslizante);
- moderação = handle em MODERATOR_HANDLES (env, vírgula-lista). Sem
  conceito novo de admin — lista explícita, decisão do dono.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from src.services.auth_common import AuthError, utcnow_iso

REPORT_CATEGORIES = ("numbers_unreal", "wrong_hardware", "wrong_model", "duplicate", "other")
REPORTS_PER_DAY = 10
FAKE_CAUGHT_POINTS = 5


def _moderator_handles() -> set[str]:
    raw = os.environ.get("MODERATOR_HANDLES", "")
    return {h.strip() for h in raw.split(",") if h.strip()}


def require_moderator(caller_user: dict[str, Any]) -> None:
    handles = _moderator_handles()
    handle = str(caller_user.get("handle", ""))
    if handle not in handles:
        raise AuthError(403, "moderation restricted to MODERATOR_HANDLES")


def _resolve_target(
    session, target_kind: str, target_id: str
) -> dict[str, Any]:
    if target_kind == "run_claim":
        target = session.find_run_claim_by_id(target_id)
    elif target_kind == "benchmark_run":
        target = session.find_run_by_id(target_id)
    else:
        raise AuthError(400, f"invalid target_kind: {target_kind}")
    if target is None:
        raise AuthError(404, f"{target_kind} not found: {target_id}")
    return target


def create_run_report(
    session,
    caller_user: dict[str, Any],
    target_kind: str,
    target_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    _resolve_target(session, target_kind, target_id)

    category = payload.get("reason_category")
    if category not in REPORT_CATEGORIES:
        raise AuthError(400, f"reason_category must be one of {REPORT_CATEGORIES}")
    detail = payload.get("reason_detail") or None
    if detail is not None and len(detail) > 1000:
        raise AuthError(400, "reason_detail too long (max 1000)")

    reporter_id = str(caller_user["id"])
    if session.count_run_reports_since(reporter_id, 24) >= REPORTS_PER_DAY:
        raise AuthError(429, f"report rate limit reached ({REPORTS_PER_DAY}/day)")

    if session.find_open_run_report(reporter_id, target_kind, target_id) is not None:
        raise AuthError(409, "you already have an open report for this target")

    now = utcnow_iso()
    record = {
        "id": str(uuid.uuid4()),
        "target_kind": target_kind,
        "run_claim_id": target_id if target_kind == "run_claim" else None,
        "benchmark_run_id": target_id if target_kind == "benchmark_run" else None,
        "reporter_user_id": reporter_id,
        "reason_category": category,
        "reason_detail": detail,
        "status": "open",
        "awarded_at": None,
        "created_at": now,
        "updated_at": now,
    }
    session.insert_run_report(record)
    session.commit()
    return {
        "id": record["id"],
        "target_kind": target_kind,
        "target_id": target_id,
        "reason_category": category,
        "status": "open",
    }


def confirm_report(session, caller_user: dict[str, Any], report_id: str) -> dict[str, Any]:
    require_moderator(caller_user)
    report = session.find_run_report_by_id(report_id)
    if report is None:
        raise AuthError(404, f"report not found: {report_id}")
    if report["status"] != "open":
        raise AuthError(409, f"report is {report['status']}, not open")

    awarded = utcnow_iso() if report.get("reporter_user_id") else None
    session.set_run_report_status(report_id, "confirmed", awarded)
    if report["target_kind"] == "run_claim":
        session.set_run_claim_status(report["run_claim_id"], "refuted")
    session.commit()
    return {"id": report_id, "status": "confirmed", "awarded": awarded is not None}


def dismiss_report(session, caller_user: dict[str, Any], report_id: str) -> dict[str, Any]:
    require_moderator(caller_user)
    report = session.find_run_report_by_id(report_id)
    if report is None:
        raise AuthError(404, f"report not found: {report_id}")
    if report["status"] != "open":
        raise AuthError(409, f"report is {report['status']}, not open")

    session.set_run_report_status(report_id, "dismissed", None)
    session.commit()
    return {"id": report_id, "status": "dismissed"}
