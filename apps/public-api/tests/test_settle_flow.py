"""S16 acceptance: settle flow — claim → signed run → settled, rep credited.

The e2e chain exercised here (all in-process, fakes per repo convention):

1. authenticated user opens a claim (S15)
2. the same account uploads a **signed** benchmark run via
   ``POST /v1/submissions`` with ``settle_claim_id`` and an Authorization
   header — the intake binds claim ↔ run but leaves it open
3. the S10 worker validates the run; ``settle_claims_for_run`` completes the
   settlement: status ``settled_verified`` + reputation events + points/tier
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from conftest import make_passkey_session, sample_report_dict, sign_report
from src.main import create_app

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKER_SRC = _REPO_ROOT / "apps" / "intake-worker" / "src"
if str(_WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(_WORKER_SRC))

from settle_claims import settle_claims_for_run  # noqa: E402


@pytest.fixture()
def client(database):
    app = create_app()
    from fastapi.testclient import TestClient
    from src.dependencies.database_session_provider import get_database_session

    app.dependency_overrides[get_database_session] = lambda: database
    with TestClient(app) as test_client:
        yield test_client


class PipelineRepo:
    """Worker-side view over FakeDatabase: adds dimension/duplicate stubs."""

    def __init__(self, database, duplicate_exists=False, peer_decode_values=None, peer_count=0):
        self.database = database
        self.duplicate_exists = duplicate_exists
        self.peer_decode_values = peer_decode_values or []
        self.peer_count = peer_count
        self.statuses = {}
        self.assessments = {}

    def find_existing_run_in_group(self, dimension, exclude_run_id, statuses):
        return self.duplicate_exists

    def fetch_peer_decode_values(self, dimension, exclude_run_id):
        return list(self.peer_decode_values)

    def count_peers(self, dimension):
        return self.peer_count

    def record_trust_assessment(self, run_id, assessment):
        self.assessments[run_id] = assessment

    def set_run_status(self, run_id, status, trust_score):
        self.statuses[run_id] = (status, trust_score)

    def publish_ranking_update(self, event):
        pass

    def fetch_settlement_context(self, run_id):
        return self.database.fetch_settlement_context(run_id)

    def complete_claim_settlement(self, **kwargs):
        return self.database.complete_claim_settlement(**kwargs)


def _signed_multipart(report_dict, private_key, model_release_id=None, settle_claim_id=None):
    digest, signature = sign_report(private_key, report_dict)
    data = {
        "report": json.dumps(report_dict),
        "signature": signature,
        "payload_digest": digest,
        "challenge_nonce": "nonce-abc",
        "client_version": "0.1.0",
        "model_release_id": model_release_id or "",
    }
    if settle_claim_id:
        data["settle_claim_id"] = settle_claim_id
    artifact = b"stdout log"  # matches sample_report_dict() declared sha256
    files = [("artifact_0", ("artifact_0", artifact, "application/octet-stream"))]
    return data, files


def test_tier_ladder_boundaries():
    from reputation_policy import tier_for_points

    assert tier_for_points(0) == "L0"
    assert tier_for_points(99) == "L0"
    assert tier_for_points(100) == "L1"
    assert tier_for_points(339) == "L1"
    assert tier_for_points(340) == "L2"
    assert tier_for_points(750) == "L3"
    assert tier_for_points(1500) == "L4"


def test_full_settle_flow_credits_reputation(client, database, monkeypatch, trusted_key):
    token = make_passkey_session(client, database, monkeypatch, "ada")
    auth = {"Authorization": f"Bearer {token}"}

    # 1. claim (claimed decode: 18.7 tok/s on the seeded model)
    claim = client.post(
        "/v1/claims",
        json={
            "model_release_id": "model-qwen25-coder-7b",
            "claimed_metrics": {"decode_tok_s": 18.7},
        },
        headers=auth,
    ).json()

    # 2. signed run upload settling the claim
    report = sample_report_dict()
    data, files = _signed_multipart(report, trusted_key, model_release_id="model-qwen25-coder-7b", settle_claim_id=claim["id"])
    response = client.post("/v1/submissions", data=data, files=files, headers=auth)
    assert response.status_code == 202, response.text
    body = response.json()
    run_id = body["run_id"]
    assert body["linked_claim_id"] == claim["id"]

    # bound but still open until validation finishes
    fetched = client.get(f"/v1/claims/{claim['id']}").json()
    assert fetched["benchmark_run_id"] == run_id
    assert fetched["status"] == "open"

    # 3. worker validates → settlement completes
    payload = json.loads(
        (_REPO_ROOT / "apps" / "intake-worker" / "tests" / "fixtures" / "valid_run.json").read_text()
    )
    payload["run_id"] = run_id
    result = process_and_assert_validated(PipelineRepo(database), run_id, payload)

    assert result["claim_settlement"]["points_awarded"] == 25
    assert result["claim_settlement"]["tier"] == "L0"

    final = client.get(f"/v1/claims/{claim['id']}").json()
    assert final["status"] == "settled_verified"

    profile = client.get("/v1/users/ada").json()
    assert profile["reputation"]["points"] == 25


def process_and_assert_validated(repo, run_id, payload):
    from worker import STATUS_VALIDATED, process_run

    result = process_run(payload, repo)
    assert result["status"] == STATUS_VALIDATED, result
    assert repo.statuses[run_id][0] == STATUS_VALIDATED
    return result


def test_disputed_claim_settlement_earns_bonus(client, database, monkeypatch, trusted_key):
    token_a = make_passkey_session(client, database, monkeypatch, "ada")
    token_b = make_passkey_session(client, database, monkeypatch, "grace")
    claim = client.post(
        "/v1/claims",
        json={"model_release_id": "model-qwen25-coder-7b", "claimed_metrics": {"decode_tok_s": 18.7}},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()
    # community doubts it (impossible vote)
    client.post(
        f"/v1/claims/{claim['id']}/votes", json={"verdict": "impossible"}, headers={"Authorization": f"Bearer {token_b}"}
    )

    report = sample_report_dict()
    data, files = _signed_multipart(report, trusted_key, model_release_id="model-qwen25-coder-7b", settle_claim_id=claim["id"])
    uploaded = client.post(
        "/v1/submissions",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    run_id = uploaded.json()["run_id"]

    fixture = json.loads((_REPO_ROOT / "apps" / "intake-worker" / "tests" / "fixtures" / "valid_run.json").read_text())
    fixture["run_id"] = run_id
    result = process_and_assert_validated(PipelineRepo(database), run_id, fixture)

    assert result["claim_settlement"]["points_awarded"] == 40  # 25 base + 15 disputed bonus
    assert len(database._reputation_events) == 2


def test_anonymous_settle_attempt_rejected(client, database, monkeypatch, trusted_key):
    token = make_passkey_session(client, database, monkeypatch, "ada")
    claim = client.post(
        "/v1/claims",
        json={"model_release_id": "model-qwen25-coder-7b", "claimed_metrics": {"decode_tok_s": 18.7}},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    report = sample_report_dict()
    data, files = _signed_multipart(report, trusted_key, model_release_id="model-qwen25-coder-7b", settle_claim_id=claim["id"])
    response = client.post(
        "/v1/submissions",
        data=data,
        files=files,
    )  # no Authorization header
    assert response.status_code == 401
    assert client.get(f"/v1/claims/{claim['id']}").json()["status"] == "open"


def test_foreign_or_unknown_claim_rejected(client, database, monkeypatch, trusted_key):
    token_a = make_passkey_session(client, database, monkeypatch, "ada")
    token_b = make_passkey_session(client, database, monkeypatch, "grace")
    claim = client.post(
        "/v1/claims",
        json={"model_release_id": "model-qwen25-coder-7b", "claimed_metrics": {"decode_tok_s": 18.7}},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()

    f_data, f_files = _claim_multipart(trusted_key, claim["id"])
    foreign = client.post(
        "/v1/submissions",
        data=f_data,
        files=f_files,
        headers={"Authorization": f"Bearer {token_b}"},
    )
    g_data, g_files = _claim_multipart(trusted_key, str(__import__("uuid").uuid4()))
    ghost = client.post(
        "/v1/submissions",
        data=g_data,
        files=g_files,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert foreign.status_code == 403
    assert ghost.status_code == 404


def _claim_multipart(trusted_key, claim_id):
    report = sample_report_dict()
    return _signed_multipart(report, trusted_key, model_release_id="model-qwen25-coder-7b", settle_claim_id=claim_id)


def test_model_mismatch_rejected(client, database, monkeypatch, trusted_key):
    token = make_passkey_session(client, database, monkeypatch, "ada")
    claim = client.post(
        "/v1/claims",
        json={"model_release_id": "model-qwen25-coder-32b", "claimed_metrics": {"decode_tok_s": 9.9}},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    data, files = _signed_multipart(sample_report_dict(), trusted_key, model_release_id="model-qwen25-coder-7b", settle_claim_id=claim["id"])
    response = client.post(
        "/v1/submissions",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]


def test_rejected_run_leaves_claim_open(client, database, monkeypatch, trusted_key):
    token = make_passkey_session(client, database, monkeypatch, "ada")
    claim = client.post(
        "/v1/claims",
        json={"model_release_id": "model-qwen25-coder-7b", "claimed_metrics": {"decode_tok_s": 18.7}},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    report = sample_report_dict()
    data, files = _signed_multipart(report, trusted_key, model_release_id="model-qwen25-coder-7b", settle_claim_id=claim["id"])
    uploaded = client.post(
        "/v1/submissions",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    run_id = uploaded.json()["run_id"]

    # a fraudulent variant fails validation in the worker
    fraudulent = json.loads(
        (_REPO_ROOT / "apps" / "intake-worker" / "tests" / "fixtures" / "fraudulent_run.json").read_text()
    )
    fraudulent["run_id"] = run_id
    from worker import process_run

    repo = PipelineRepo(database)
    result = process_run(fraudulent, repo)
    assert result["status"] != "validated"
    assert result["claim_settlement"] is None
    assert client.get(f"/v1/claims/{claim['id']}").json()["status"] == "open"


def test_second_run_cannot_rebind_settled_claim(client, database, monkeypatch, trusted_key):
    token = make_passkey_session(client, database, monkeypatch, "ada")
    claim = client.post(
        "/v1/claims",
        json={"model_release_id": "model-qwen25-coder-7b", "claimed_metrics": {"decode_tok_s": 18.7}},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    data, files = _signed_multipart(sample_report_dict(), trusted_key, model_release_id="model-qwen25-coder-7b", settle_claim_id=claim["id"])
    first = client.post(
        "/v1/submissions",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert database.bind_claim_to_run(claim["id"], first["run_id"]) == 0  # already bound at intake
