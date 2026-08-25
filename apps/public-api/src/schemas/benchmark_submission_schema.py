"""Pydantic v2 models for the benchmark submission endpoint (S01 contract).

The endpoint receives ``multipart/form-data``; the string fields below are
collected from the form and validated against this model. ``model_release_id``,
``quantization_profile_id`` and ``inference_runtime_id`` are forward-compatible
overrides: the 0.9.0 report does not carry catalog bindings, so when absent the
intake service resolves them deterministically (see ``submit_benchmark_run``).
"""

from pydantic import BaseModel


class SubmissionForm(BaseModel):
    report: str
    signature: str
    payload_digest: str
    challenge_nonce: str
    client_version: str
    model_release_id: str | None = None
    quantization_profile_id: str | None = None
    inference_runtime_id: str | None = None


class SubmissionAccepted(BaseModel):
    run_id: str
