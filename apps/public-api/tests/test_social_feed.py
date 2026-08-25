"""S17 tests: follow graph, notifications and the feed."""

from __future__ import annotations

import pytest

from conftest import make_passkey_session
from src.main import create_app

HANDLE_A = "ada"
HANDLE_B = "grace"


@pytest.fixture()
def client(database):
    app = create_app()
    from fastapi.testclient import TestClient
    from src.dependencies.database_session_provider import get_database_session

    app.dependency_overrides[get_database_session] = lambda: database
    with TestClient(app) as test_client:
        yield test_client


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- follow graph ------------------------------------------------------------


def test_follow_requires_auth(client):
    assert client.post("/v1/users/grace/follow").status_code == 401


def test_follow_unfollow_and_counts(client, database, monkeypatch):
    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    token_b = make_passkey_session(client, database, monkeypatch, HANDLE_B)

    followed = client.post("/v1/users/ada/follow", headers=_auth(token_b))
    assert followed.status_code == 200
    assert followed.json()["is_following"] is True
    assert followed.json()["followers"] == 1

    duplicate = client.post("/v1/users/ada/follow", headers=_auth(token_b))
    assert duplicate.status_code == 409

    self_follow = client.post("/v1/users/grace/follow", headers=_auth(token_b))
    assert self_follow.status_code == 400

    unknown = client.post("/v1/users/ghost/follow", headers=_auth(token_b))
    assert unknown.status_code == 404

    # profile reflects the edge + viewer perspective
    as_stranger = client.get("/v1/users/ada").json()
    as_follower = client.get("/v1/users/ada", headers=_auth(token_b)).json()
    assert as_stranger["follow"] == {"followers": 1, "following": 0, "viewer_is_following": False}
    assert as_follower["follow"]["viewer_is_following"] is True

    removed = client.delete("/v1/users/ada/follow", headers=_auth(token_b))
    assert removed.status_code == 200
    missing = client.delete("/v1/users/ada/follow", headers=_auth(token_b))
    assert missing.status_code == 404


def test_new_follower_notification(client, database, monkeypatch):
    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    token_b = make_passkey_session(client, database, monkeypatch, HANDLE_B)
    client.post("/v1/users/ada/follow", headers=_auth(token_b))

    notes_a = client.get("/v1/notifications", headers=_auth(token_a)).json()
    kinds = [n["kind"] for n in notes_a]
    assert "new_follower" in kinds
    assert all(n["recipient_id"] == database.find_app_user_by_handle(HANDLE_A)["id"] for n in notes_a)

    target = notes_a[0]
    read = client.post(f"/v1/notifications/{target['id']}/read", headers=_auth(token_a))
    assert read.json() == {"read": True}
    again = client.post(f"/v1/notifications/{target['id']}/read", headers=_auth(token_a))
    assert again.status_code == 404

    anon = client.get("/v1/notifications")
    assert anon.status_code == 401


# --- feed --------------------------------------------------------------------


def test_feed_scopes_and_trending_sort(client, database, monkeypatch, trusted_key):
    from conftest import sample_report_dict, sign_report

    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    token_b = make_passkey_session(client, database, monkeypatch, HANDLE_B)

    # A claims + settles a run; B claims something too
    claim_a = client.post(
        "/v1/claims",
        json={"model_release_id": "model-qwen25-coder-7b", "claimed_metrics": {"decode_tok_s": 18.7}},
        headers=_auth(token_a),
    ).json()
    digest, signature = sign_report(trusted_key, sample_report_dict())
    upload = client.post(
        "/v1/submissions",
        data={
            "report": __import__("json").dumps(sample_report_dict()),
            "signature": signature,
            "payload_digest": digest,
            "challenge_nonce": "n",
            "client_version": "0.1.0",
            "model_release_id": "model-qwen25-coder-7b",
            "settle_claim_id": claim_a["id"],
        },
        files=[("artifact_0", ("a0", b"stdout log", "application/octet-stream"))],
        headers=_auth(token_a),
    )
    assert upload.status_code == 202, upload.text
    client.post(
        "/v1/claims",
        json={"model_release_id": "model-qwen25-coder-32b", "claimed_metrics": {"decode_tok_s": 9.9}},
        headers=_auth(token_b),
    )

    global_feed = client.get("/v1/feed?scope=global").json()
    types = {item["type"] for item in global_feed}
    assert "claim" in types and "verified_run" in types

    # anonymous following-scope feed is empty (no graph for anonymous)
    assert client.get("/v1/feed?scope=following").json() == []

    # B follows nobody yet -> empty; after following A, A's items appear
    following_b = client.get("/v1/feed?scope=following", headers=_auth(token_b)).json()
    assert following_b == []
    client.post("/v1/users/ada/follow", headers=_auth(token_b))

    following_b = client.get("/v1/feed?scope=following", headers=_auth(token_b)).json()
    handles_in_feed = {item.get("handle") for item in following_b if item["type"] == "claim"}
    assert handles_in_feed == {HANDLE_A}
    assert all(item.get("handle") != HANDLE_B for item in following_b if item["type"] == "claim")

    trending = client.get("/v1/feed?scope=global&sort=trending").json()
    assert len(trending) >= 2
    bad_scope = client.get("/v1/feed?scope=galaxy")
    assert bad_scope.status_code == 400


def test_settlement_creates_notification_for_claimant(client, database, monkeypatch, trusted_key):
    """Worker-side settlement leaves a notification the claimant can read."""
    token_a = make_passkey_session(client, database, monkeypatch, HANDLE_A)
    claim = client.post(
        "/v1/claims",
        json={"model_release_id": "model-qwen25-coder-7b", "claimed_metrics": {"decode_tok_s": 18.7}},
        headers=_auth(token_a),
    ).json()

    from conftest import sample_report_dict, sign_report
    import json as jsonlib

    digest, signature = sign_report(trusted_key, sample_report_dict())
    upload = client.post(
        "/v1/submissions",
        data={
            "report": jsonlib.dumps(sample_report_dict()),
            "signature": signature,
            "payload_digest": digest,
            "challenge_nonce": "n",
            "client_version": "0.1.0",
            "model_release_id": "model-qwen25-coder-7b",
            "settle_claim_id": claim["id"],
        },
        files=[("artifact_0", ("a0", b"stdout log", "application/octet-stream"))],
        headers=_auth(token_a),
    )
    run_id = upload.json()["run_id"]

    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    worker_src = str(repo_root / "apps" / "intake-worker" / "src")
    if worker_src not in sys.path:
        sys.path.insert(0, worker_src)

    from worker import process_run
    payload = jsonlib.loads(
        (repo_root / "apps" / "intake-worker" / "tests" / "fixtures" / "valid_run.json").read_text()
    )
    payload["run_id"] = run_id

    class Repo:
        def __init__(self, db):
            self.database = db
            self.statuses = {}

        def find_existing_run_in_group(self, dimension, exclude_run_id, statuses):
            return False

        def fetch_peer_decode_values(self, dimension, exclude_run_id):
            return []

        def count_peers(self, dimension):
            return 0

        def record_trust_assessment(self, run_id, assessment):
            self.statuses[run_id] = assessment

        def set_run_status(self, run_id, status, trust_score):
            self.database.set_run_status(run_id, status, trust_score) if hasattr(
                self.database, "set_run_status"
            ) else None

        def publish_ranking_update(self, event):
            pass

        def fetch_settlement_context(self, run_id):
            return self.database.fetch_settlement_context(run_id)

        def complete_claim_settlement(self, **kwargs):
            self.database.complete_claim_settlement(**kwargs)

    process_run(payload, Repo(database))

    notes = client.get("/v1/notifications", headers=_auth(token_a)).json()
    kinds = [n["kind"] for n in notes]
    assert "claim_settled_verified" in kinds
