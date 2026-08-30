"""S23 API end to end: per-user signing keys over the real routes.

Register a key (bearer), submit a run signed by the CALLER's key and read
the attribution back; another user's key is 403; a revoked key is 400; an
invalid signature is 400; the legacy global-key path stays intact; only
ed25519 PEMs are accepted at registration.
"""

from __future__ import annotations

import json

from conftest import make_passkey_session, sample_report_dict, sign_report
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _pem(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _register_key(client, token: str, private_key: Ed25519PrivateKey) -> dict:
    response = client.post(
        "/v1/auth/signing-keys",
        headers={"Authorization": f"Bearer {token}"},
        json={"label": "rig", "public_key_pem": _pem(private_key)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _submit(
    client,
    report: dict,
    signer: Ed25519PrivateKey,
    signature_key_id: str | None = None,
    token: str | None = None,
):
    digest, signature = sign_report(signer, report)
    data = {
        "report": json.dumps(report),
        "signature": signature,
        "payload_digest": digest,
        "challenge_nonce": "nonce-s23",
        "client_version": "s23-test",
    }
    if signature_key_id:
        data["signature_key_id"] = signature_key_id
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    files = [("artifact_0", ("artifact_0", b"stdout log", "application/octet-stream"))]
    return client.post("/v1/submissions", data=data, files=files, headers=headers)


def test_register_list_revoke_and_attribute(
    client, database, trusted_key, monkeypatch
) -> None:
    token = make_passkey_session(client, database, monkeypatch, "s23-signer")
    user_key = Ed25519PrivateKey.generate()

    created = _register_key(client, token, user_key)
    assert created["algorithm"] == "ed25519" and created["run_count"] == 0

    listed = client.get(
        "/v1/auth/signing-keys", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert [row["id"] for row in listed] == [created["id"]]

    # signed submission attributed to the user's key
    report = sample_report_dict()
    response = _submit(client, report, user_key, signature_key_id=created["id"], token=token)
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    stored = database.find_run_by_id(run_id)
    assert stored is not None and stored["signature_key_id"] == created["id"]

    listed = client.get(
        "/v1/auth/signing-keys", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert listed[0]["run_count"] == 1

    revoked = client.delete(
        f"/v1/auth/signing-keys/{created['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoked.status_code == 200 and revoked.json()["revoked_at"]

    # a revoked key no longer vouches for new submissions
    report2 = sample_report_dict()
    report2["run_id"] = "01J9XYZTEST0000000000000S23B"
    response = _submit(client, report2, user_key, signature_key_id=created["id"], token=token)
    assert response.status_code == 400
    assert "revoked" in response.json()["detail"]


def test_signature_with_someone_elses_key_is_403(
    client, database, trusted_key, monkeypatch
) -> None:
    owner_token = make_passkey_session(client, database, monkeypatch, "s23-owner")
    other_token = make_passkey_session(client, database, monkeypatch, "s23-other")
    owner_key = Ed25519PrivateKey.generate()
    created = _register_key(client, owner_token, owner_key)

    report = sample_report_dict()
    response = _submit(client, report, owner_key, signature_key_id=created["id"], token=other_token)
    assert response.status_code == 403
    assert "another user" in response.json()["detail"]


def test_invalid_signature_with_user_key_is_400(
    client, database, trusted_key, monkeypatch
) -> None:
    token = make_passkey_session(client, database, monkeypatch, "s23-badsig")
    user_key = Ed25519PrivateKey.generate()
    created = _register_key(client, token, user_key)

    report = sample_report_dict()
    # signed by the GLOBAL key while claiming the user's key id → mismatch
    response = _submit(client, report, trusted_key, signature_key_id=created["id"], token=token)
    assert response.status_code == 400
    assert "signature verification failed" in response.json()["detail"]


def test_legacy_global_key_path_still_works(client, database, trusted_key) -> None:
    report = sample_report_dict()
    response = _submit(client, report, trusted_key)
    assert response.status_code == 202, response.text
    stored = database.find_run_by_id(response.json()["run_id"])
    assert stored is not None and stored["signature_key_id"] is None


def test_register_rejects_non_ed25519_pem(client, database, monkeypatch) -> None:
    from cryptography.hazmat.primitives.asymmetric import rsa

    token = make_passkey_session(client, database, monkeypatch, "s23-rsa")
    pem = rsa.generate_private_key(public_exponent=65537, key_size=2048) \
        .public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
    response = client.post(
        "/v1/auth/signing-keys",
        headers={"Authorization": f"Bearer {token}"},
        json={"label": "rsa", "public_key_pem": pem},
    )
    assert response.status_code == 400
    assert "ed25519" in response.json()["detail"]
