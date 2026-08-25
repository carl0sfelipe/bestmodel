"""Passkey authentication ceremony (S13).

1. ``passkey_login_options`` — returns PublicKeyCredentialRequestOptions for
   the handle's registered credentials, with a server-stored challenge.
2. ``verify_passkey_authentication`` — verifies the assertion against the
   stored public key and signature counter, then issues a short-lived session
   bearer token (``auth_token.kind = 'session'``).
"""

from __future__ import annotations

import base64
import json
from typing import Any

from src.dependencies.auth_provider import WebAuthnConfig
from src.services.auth_common import AuthError, expiry_iso, issue_token, utcnow_iso
from src.services.register_passkey import _encode, _normalize_handle


def passkey_login_options(session, config: WebAuthnConfig, handle: str) -> dict[str, Any]:
    user = _require_user(session, handle)
    credentials = session.fetch_webauthn_credentials_by_user(user["id"])
    if not credentials:
        raise AuthError(404, "no passkeys registered for this handle")

    options = _generate_authentication_options(
        rp_id=config.rp_id,
        allow_credentials=[
            {"id": row["credential_id"], "transports": list(row.get("transports") or [])}
            for row in credentials
        ],
    )
    session.insert_auth_challenge(
        {
            "challenge": _encode(options.challenge),
            "purpose": "authentication",
            "app_user_id": user["id"],
            "expires_at": expiry_iso(config.challenge_ttl_seconds),
        }
    )
    session.commit()
    return {"user_id": user["id"], "options": json.loads(_options_to_json(options))}


def verify_passkey_authentication(
    session,
    config: WebAuthnConfig,
    handle: str,
    credential: dict[str, Any],
) -> dict[str, Any]:
    user = _require_user(session, handle)

    response = credential.get("response") if isinstance(credential, dict) else None
    challenge_b64 = (response or {}).get("challenge")
    if not challenge_b64:
        raise AuthError(400, "credential.response.challenge is required")

    record = session.fetch_auth_challenge(str(challenge_b64))
    if (
        record is None
        or record["purpose"] != "authentication"
        or record["app_user_id"] != user["id"]
    ):
        raise AuthError(400, "unknown or invalid challenge")

    stored = _find_stored_credential(session, user["id"], credential)
    try:
        from webauthn import base64url_to_bytes

        verification = _verify_assertion(
            config=config,
            credential=credential,
            expected_challenge=base64url_to_bytes(str(challenge_b64)),
            credential_public_key=stored["public_key"],
            credential_current_sign_count=stored["sign_count"],
        )
    except Exception as exc:
        raise AuthError(400, f"assertion verification failed: {exc}") from exc

    session.update_webauthn_credential_sign_count(
        stored["credential_id"], verification.new_sign_count, utcnow_iso()
    )

    _, plaintext = issue_token(
        session,
        user_id=user["id"],
        kind="session",
        name=None,
        expires_at=expiry_iso(config.session_ttl_seconds),
    )
    session.delete_auth_challenge(str(challenge_b64))
    session.commit()
    return {
        "access_token": plaintext,
        "token_type": "bearer",
        "expires_at": expiry_iso(config.session_ttl_seconds),
    }


def _require_user(session, handle: str) -> dict[str, Any]:
    normalized = _normalize_handle(handle)
    user = session.find_app_user_by_handle(normalized)
    if user is None:
        raise AuthError(404, f"unknown handle: {normalized}")
    return user


def _find_stored_credential(session, user_id: str, credential: dict[str, Any]) -> dict[str, Any]:
    raw_id_b64 = (credential.get("rawId") or credential.get("id") or "").strip()
    if not raw_id_b64:
        raise AuthError(400, "credential.rawId is required")
    for row in session.fetch_webauthn_credentials_by_user(user_id):
        encoded = base64.urlsafe_b64encode(bytes(row["credential_id"])).decode().rstrip("=")
        if encoded == raw_id_b64.rstrip("="):
            return row
    raise AuthError(400, "credential is not registered for this handle")


# --- webauthn-package wrappers (patch points for tests) ---------------------


def _generate_authentication_options(rp_id: str, allow_credentials: list[dict]):
    from webauthn import generate_authentication_options
    from webauthn.helpers.structs import PublicKeyCredentialDescriptor

    return generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=[
            PublicKeyCredentialDescriptor(
                id=item["id"],
                transports=list(item.get("transports") or []) or None,
            )
            for item in allow_credentials
        ],
    )


def _options_to_json(options: Any) -> str:
    from webauthn import options_to_json

    return options_to_json(options)


def _verify_assertion(
    config: WebAuthnConfig,
    credential: dict[str, Any],
    expected_challenge: bytes,
    credential_public_key: bytes,
    credential_current_sign_count: int,
):
    from webauthn import verify_authentication_response

    return verify_authentication_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_origin=config.expected_origin,
        expected_rp_id=config.rp_id,
        credential_public_key=credential_public_key,
        credential_current_sign_count=credential_current_sign_count,
        require_user_verification=False,
    )
