"""Passkey registration ceremony (S13, passkey-first per L02).

Two calls:

1. ``passkey_registration_options`` — creates the account on first contact and
   returns PublicKeyCredentialCreationOptions plus a server-stored challenge.
2. ``verify_passkey_registration`` — verifies the attestation against the
   stored challenge and persists the credential.

WebAuthn cryptography is delegated to the ``webauthn`` package through thin
wrappers (``_generate_registration_options`` / ``_verify_attestation``) so the
orchestration stays unit-testable without a hardware authenticator.
"""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any

from src.dependencies.auth_provider import WebAuthnConfig
from src.services.auth_common import (
    AuthError,
    HANDLE_PATTERN_ERROR,
    expiry_iso,
    utcnow_iso,
)

CHALLENGE_TTL_FALLBACK_SECONDS = 120


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def passkey_registration_options(
    session,
    config: WebAuthnConfig,
    handle: str,
    display_name: str | None,
) -> dict[str, Any]:
    handle = _normalize_handle(handle)
    user = session.find_app_user_by_handle(handle)
    if user is None:
        user = {
            "id": str(uuid.uuid4()),
            "handle": handle,
            "display_name": display_name or handle,
        }
        session.insert_app_user(user)
        session.commit()

    existing = session.fetch_webauthn_credentials_by_user(user["id"])
    options = _generate_registration_options(
        config=config,
        user=user,
        excluded_credential_ids=[row["credential_id"] for row in existing],
    )
    session.insert_auth_challenge(
        {
            "challenge": _encode(options.challenge),
            "purpose": "registration",
            "app_user_id": user["id"],
            "expires_at": expiry_iso(
                config.challenge_ttl_seconds or CHALLENGE_TTL_FALLBACK_SECONDS
            ),
        }
    )
    session.commit()
    return {"user_id": user["id"], "options": json.loads(_options_to_json(options))}


def verify_passkey_registration(
    session,
    config: WebAuthnConfig,
    handle: str,
    credential: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    handle = _normalize_handle(handle)
    user = session.find_app_user_by_handle(handle)
    if user is None:
        raise AuthError(404, f"unknown handle: {handle}")

    challenge_record = _consume_valid_challenge(session, config, user["id"], credential)
    try:
        verification = _verify_attestation(
            config=config,
            credential=credential,
            expected_challenge=challenge_record["challenge_bytes"],
        )
    except Exception as exc:
        raise AuthError(400, f"attestation verification failed: {exc}") from exc

    record = {
        "id": str(uuid.uuid4()),
        "app_user_id": user["id"],
        "credential_id": verification.credential_id,
        "public_key": verification.credential_public_key,
        "sign_count": verification.sign_count,
        "transports": [],
        "created_at": utcnow_iso(),
        "last_used_at": None,
    }
    session.insert_webauthn_credential(record)
    session.delete_auth_challenge(challenge_record["challenge"])
    session.commit()
    return 201, {"user_id": user["id"], "credential_id": verification.credential_id.hex()}


def _consume_valid_challenge(
    session, config: WebAuthnConfig, user_id: str, credential: dict[str, Any]
) -> dict[str, Any]:
    from webauthn import base64url_to_bytes

    response = credential.get("response") if isinstance(credential, dict) else None
    challenge_b64 = (response or {}).get("challenge")
    if not challenge_b64:
        raise AuthError(400, "credential.response.challenge is required")

    record = session.fetch_auth_challenge(str(challenge_b64))
    if record is None:
        raise AuthError(400, "unknown or expired challenge")
    if record["purpose"] != "registration" or record["app_user_id"] != user_id:
        raise AuthError(400, "challenge does not match this registration attempt")
    return {
        "challenge": str(challenge_b64),
        "challenge_bytes": base64url_to_bytes(str(challenge_b64)),
        **record,
    }


def _normalize_handle(handle: str) -> str:
    normalized = (handle or "").strip().lower()
    import re

    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,31}", normalized):
        raise AuthError(400, HANDLE_PATTERN_ERROR)
    return normalized


# --- webauthn-package wrappers (patch points for tests) ---------------------


def _generate_registration_options(config: WebAuthnConfig, user: dict, excluded_credential_ids: list[bytes]):
    from webauthn import generate_registration_options
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    return generate_registration_options(
        rp_id=config.rp_id,
        rp_name=config.rp_name,
        user_name=user["handle"],
        user_display_name=user["display_name"],
        user_id=bytes.fromhex(user["id"].replace("-", "")),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=credential_id)
            for credential_id in excluded_credential_ids
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )


def _options_to_json(options: Any) -> str:
    from webauthn import options_to_json

    return options_to_json(options)


def _verify_attestation(
    config: WebAuthnConfig,
    credential: dict[str, Any],
    expected_challenge: bytes,
):
    from webauthn import verify_registration_response

    return verify_registration_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_origin=config.expected_origin,
        expected_rp_id=config.rp_id,
        require_user_verification=False,
    )
