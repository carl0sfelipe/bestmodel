"""EaaS anchor route (B1): per-run Bitcoin-anchored evidence exposure."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.dependencies.database_session_provider import get_database_session


def test_run_anchor_returns_record_and_proof_url(client: TestClient) -> None:
    session = client.app.dependency_overrides[get_database_session]()
    session.run_anchors.append(
        {
            "run_id": "11111111-1111-1111-1111-111111111111",
            "digest": "ab" * 32,
            "record_id": "rc_" + "c" * 24,
            "studio_id": "bestmodel",
            "anchored_at": "2026-10-31T09:00:00+00:00",
        }
    )
    response = client.get("/v1/runs/11111111-1111-1111-1111-111111111111/anchor")
    assert response.status_code == 200
    body = response.json()
    assert body["record_id"].startswith("rc_")
    assert body["digest"] == "ab" * 32
    assert body["studio_id"] == "bestmodel"
    assert "/v1/records/" in body["proof_url"]


def test_run_anchor_404_when_never_anchored(client: TestClient) -> None:
    response = client.get("/v1/runs/22222222-2222-2222-2222-222222222222/anchor")
    assert response.status_code == 404
