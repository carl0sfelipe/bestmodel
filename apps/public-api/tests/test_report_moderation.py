"""Moderation: the queue, the decision, and what the decision grants.

The mural is the queue. Confirming a report is a moderation act that
refutes the target, and it is also the act that earns the reporter the
badge that says they caught a fake — so the badge and the decision are
tested together.
"""

from __future__ import annotations

import os

from conftest import make_passkey_session

REPORTER = "reporter_ada"
MODERATOR = "mod_carlos"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_claim(database, claimant_id):
    import uuid

    claim_id = str(uuid.uuid4())
    database.insert_run_claim(
        {
            "id": claim_id,
            "claimant_id": claimant_id,
            "status": "open",
            "claimed_metrics": {"decode_tok_s": 42.0},
            "prior_snapshot": {},
        }
    )
    return claim_id


def test_confirming_a_report_grants_the_reporter_the_badge(
    client, database, monkeypatch
):
    monkeypatch.setenv("MODERATOR_HANDLES", MODERATOR)
    reporter_token = make_passkey_session(client, database, monkeypatch, REPORTER)
    moderator_token = make_passkey_session(client, database, monkeypatch, MODERATOR)

    reporter = database.find_app_user_by_handle(REPORTER)
    claim_id = _seed_claim(database, reporter["id"])

    created = client.post(
        f"/v1/run-claims/{claim_id}/reports",
        headers=_auth(reporter_token),
        json={"reason_category": "numbers_unreal", "reason_detail": "the log shows nothing"},
    )
    assert created.status_code in (200, 201), created.text
    report_id = created.json()["id"]

    before = client.get(f"/v1/users/{REPORTER}").json().get("badges") or []
    assert "giant_killer" not in [badge.get("code") for badge in before]

    confirmed = client.post(
        f"/v1/reports/{report_id}/confirm", headers=_auth(moderator_token)
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["badge_granted"] is True

    after = client.get(f"/v1/users/{REPORTER}").json().get("badges") or []
    assert "giant_killer" in [badge.get("code") for badge in after]


def test_confirming_twice_grants_the_badge_once(
    client, database, monkeypatch
):
    monkeypatch.setenv("MODERATOR_HANDLES", MODERATOR)
    reporter_token = make_passkey_session(client, database, monkeypatch, REPORTER)
    moderator_token = make_passkey_session(client, database, monkeypatch, MODERATOR)

    reporter = database.find_app_user_by_handle(REPORTER)
    claim_id = _seed_claim(database, reporter["id"])
    created = client.post(
        f"/v1/run-claims/{claim_id}/reports",
        headers=_auth(reporter_token),
        json={"reason_category": "numbers_unreal"},
    )
    report_id = created.json()["id"]

    first = client.post(f"/v1/reports/{report_id}/confirm", headers=_auth(moderator_token))
    assert first.status_code == 200
    # the report is confirmed, not open: a second decision is refused
    second = client.post(f"/v1/reports/{report_id}/confirm", headers=_auth(moderator_token))
    assert second.status_code == 409

    after = client.get(f"/v1/users/{REPORTER}").json().get("badges") or []
    codes = [badge.get("code") for badge in after]
    assert codes.count("giant_killer") == 1


def test_a_non_moderator_cannot_confirm_a_report(client, database, monkeypatch):
    monkeypatch.setenv("MODERATOR_HANDLES", MODERATOR)
    reporter_token = make_passkey_session(client, database, monkeypatch, REPORTER)
    reporter = database.find_app_user_by_handle(REPORTER)
    claim_id = _seed_claim(database, reporter["id"])
    created = client.post(
        f"/v1/run-claims/{claim_id}/reports",
        headers=_auth(reporter_token),
        json={"reason_category": "numbers_unreal"},
    )
    report_id = created.json()["id"]

    refused = client.post(f"/v1/reports/{report_id}/confirm", headers=_auth(reporter_token))
    assert refused.status_code == 403

    after = client.get(f"/v1/users/{REPORTER}").json().get("badges") or []
    assert "giant_killer" not in [badge.get("code") for badge in after]


def test_a_dismissed_report_grants_nothing(client, database, monkeypatch):
    monkeypatch.setenv("MODERATOR_HANDLES", MODERATOR)
    reporter_token = make_passkey_session(client, database, monkeypatch, REPORTER)
    moderator_token = make_passkey_session(client, database, monkeypatch, MODERATOR)

    reporter = database.find_app_user_by_handle(REPORTER)
    claim_id = _seed_claim(database, reporter["id"])
    created = client.post(
        f"/v1/run-claims/{claim_id}/reports",
        headers=_auth(reporter_token),
        json={"reason_category": "numbers_unreal"},
    )
    report_id = created.json()["id"]

    dismissed = client.post(f"/v1/reports/{report_id}/dismiss", headers=_auth(moderator_token))
    assert dismissed.status_code == 200

    after = client.get(f"/v1/users/{REPORTER}").json().get("badges") or []
    assert "giant_killer" not in [badge.get("code") for badge in after]
