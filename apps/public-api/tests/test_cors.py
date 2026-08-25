"""S21 deployment tests: CORS surface required by the Vercel-hosted console."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import create_app


def _client_with_origins(monkeypatch, origins: str) -> TestClient:
    monkeypatch.setenv("CORS_ORIGINS", origins)
    return TestClient(create_app())


def test_preflight_allowed_for_configured_origin(monkeypatch):
    client = _client_with_origins(monkeypatch, "https://bestmodel.run")
    response = client.options(
        "/v1/submissions/nonce",
        headers={
            "Origin": "https://bestmodel.run",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://bestmodel.run"


def test_unlisted_origin_gets_no_cors_grant(monkeypatch):
    client = _client_with_origins(monkeypatch, "https://bestmodel.run")
    response = client.get(
        "/v1/submissions/nonce",
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 200  # API still answers…
    assert "access-control-allow-origin" not in response.headers  # …but browser will block


def test_local_dev_defaults_apply_without_env(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    client = TestClient(create_app())
    response = client.get("/v1/submissions/nonce", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
