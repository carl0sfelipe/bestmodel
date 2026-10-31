"""Anchor validated runs in the EaaS engine (B1: pool integrity evidence).

A run that reaches ``validated`` had its canonical payload digest registered
with the Cloudfair/EaaS verify-api (``POST /v1/records``). The anchor is
tamper-evidence for the pool: the digest, the kind and the timestamp end up
in a Merkle batch that is anchored on Bitcoin. Anyone can later prove that a
leaderboard cell today is the same measurement that was validated then.

Canonicalization contract (auditors must be able to recompute the digest):
``sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")))`` over
the EXACT submission payload the worker validated.

Configuration (env):
- ``EAAS_VERIFY_URL``   — verify-api base (default http://127.0.0.1:8080)
- ``EAAS_API_KEY``      — tenant API key (eak_...) with scope ``record``.
  Absent ⇒ anchoring DISABLED (log once per worker start; validation flow
  is unaffected).

Failure policy: an anchor failure NEVER fails or delays run validation —
the run simply stays unanchored (a later sweep can re-anchor; first anchor
wins via ON CONFLICT DO NOTHING).
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from typing import Any, Callable, Protocol

STUDIO_ID = "bestmodel"
RECORD_KIND = "benchmark"
_TIMEOUT_SECONDS = 5


class AnchorRepository(Protocol):
    def record_anchor(
        self, run_id: str, digest: str, record_id: str, studio_id: str
    ) -> None: ...


def canonical_run_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def anchor_config() -> tuple[str | None, str]:
    """(api_key, verify_url); api_key None ⇒ anchoring disabled."""
    key = os.environ.get("EAAS_API_KEY", "").strip()
    base = os.environ.get("EAAS_VERIFY_URL", "http://127.0.0.1:8080").strip().rstrip("/")
    return (key or None), base


def _urllib_post(url: str, body: dict[str, Any], bearer: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {bearer}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def anchor_validated_run(
    run_id: str,
    payload: dict[str, Any],
    repository: AnchorRepository,
    http_post: Callable[[str, dict[str, Any], str], dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Register the run's canonical digest. Returns the engine receipt or
    None when disabled. Raises on transport/API failure — the caller
    (worker) decides to swallow (validation must not fail because of it)."""
    # Late binding: testes substituem o transporte pelo atributo do módulo.
    if http_post is None:
        http_post = globals()["_urllib_post"]
    api_key, base = anchor_config()
    if api_key is None:
        return None
    digest = canonical_run_digest(payload)
    response = http_post(
        f"{base}/v1/records",
        {
            "studio_id": STUDIO_ID,
            "kind": RECORD_KIND,
            "digest": digest,
            "reference": run_id,
        },
        api_key,
    )
    record_id = response.get("record_id")
    if not record_id:
        raise ValueError(f"engine did not return a record_id: {response!r}")
    repository.record_anchor(run_id, digest, record_id, STUDIO_ID)
    return {
        "record_id": record_id,
        "digest": digest,
        "duplicate": bool(response.get("duplicate")),
        "studio_id": STUDIO_ID,
    }
