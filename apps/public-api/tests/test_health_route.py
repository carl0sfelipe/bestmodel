"""H12: /v1/health reports the baked-in commit; unknown when not built."""


def test_health_reports_git_sha_from_env(client, monkeypatch):
    monkeypatch.setenv("BESTMODEL_GIT_SHA", "abc123def456")
    monkeypatch.setenv("BESTMODEL_BUILT_AT", "2026-09-19T20:00:00Z")
    body = client.get("/v1/health").json()
    assert body["status"] == "ok"
    assert body["git_sha"] == "abc123def456"
    assert body["built_at"] == "2026-09-19T20:00:00Z"
    assert body["service"] == "public-api"


def test_health_is_honest_when_unbuilt(client, monkeypatch):
    monkeypatch.delenv("BESTMODEL_GIT_SHA", raising=False)
    assert client.get("/v1/health").json()["git_sha"] == "unknown"
