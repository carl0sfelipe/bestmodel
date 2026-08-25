# S08: CLI report generation, signing, and upload (sign + upload)

## Goal

In `cli/benchmark-probe` (Rust), implement CLI responsibilities 7–10 of Section 9.3 of the plan: generate a structured JSON report conforming to contract 0.9.0, compute SHA-256 for the payload and artifacts, sign with a local Ed25519 key, and upload via the Submission API (Section 12.1). S07 already delivered topology collection, runtime detection, scenario execution, and metric parsing; this wave completes the signing and upload chain.

## Dependencies

- S07 (`cli/benchmark-probe`: topology collection, runtime detection, scenario execution, metric parsing; the S07 spec notes that `sign_submission_payload.rs` and `upload_benchmark_report.rs` are deferred to this wave)

## Wave

W4

## Deliverables

| Path | Description |
|---|---|
| `cli/benchmark-probe/src/sign_submission_payload.rs` | Build 0.9.0 report JSON, canonicalize payload, compute `payload_digest`, Ed25519 signing |
| `cli/benchmark-probe/src/upload_benchmark_report.rs` | Compute SHA-256 for artifacts, assemble upload request, submit via HTTP to the Submission API |
| `cli/benchmark-probe/Cargo.toml` | Add dependencies: `ed25519-dalek`, `sha2`, `serde_json`, `reqwest` (blocking), `hex`, etc. |
| `cli/benchmark-probe/tests/test_sign_submission_payload.rs` | Signing / verification roundtrip test (test keys) |
| `cli/benchmark-probe/tests/test_upload_benchmark_report.rs` | Upload test (local mock HTTP server, returns challenge nonce) |

## Technical Requirements

Reference Section 9.3 (from the original internal design doc) (CLI Benchmark Engine design) and Section 12.1 (CLI cryptography and signing).

### Structured report (9.3 internal structured output)

`sign_submission_payload.rs` generates the report JSON; the fields are verbatim consistent with the example in Section 9.3:

- `schema_version` fixed to `"0.9.0"`
- `run_id`, `runtime`, `runtime_version`, `hardware_fingerprint`
- `scenario`: `prompt_tokens`, `generated_tokens`, `batch_size`, `context_tokens`
- `metrics`: `ttft_ms`, `prefill_tok_s`, `decode_tok_s`, `peak_vram_mib`, `power_watt_avg`
- `artifacts`: `[{ "artifact_kind": "...", "sha256": "..." }]`

### Canonicalize and payload digest (12.1)

- canonicalized payload = deterministic JSON serialization (sorted keys, compact output, fixed field order)
- `payload_digest = SHA256(canonicalized_payload)`, output in `sha256:<hex>` form
- `artifact_digest = SHA256(file_bytes)`, computed per artifact file

### Ed25519 local signing (12.1)

- Key path is specified by the environment variable `BENCHMARK_PROBE_KEY_PATH`; default is `~/.config/benchmark-probe/ed25519.pem`
- If the key does not exist, generate automatically and write to that path; signing uses the local Ed25519 private key
- The signed object is `payload_digest`; output `signature` (hex)

### Upload (12.1 fields carried in upload)

`upload_benchmark_report.rs` performs the upload after signing:

1. First request `challenge_nonce` from the platform (Submission API, `GET /v1/submissions/nonce`, see S09)
2. POST with `multipart/form-data` to `POST /v1/submissions` (Submission API, see S09), carrying:
   - `report`: 0.9.0 report JSON string
   - `signature`, `payload_digest`, `challenge_nonce`, `client_version`
   - artifact files: named `artifact_0`, `artifact_1`, … by the index in the `artifacts` list of the report
3. API base URL is specified by the environment variable `BENCHMARK_PROBE_API_URL`; default `http://localhost:8000`
4. Non-2xx response: output a clear error with the status code and exit with a non-zero exit code

### Tests

- `test_sign_submission_payload.rs`: sign and verify with a test-generated Ed25519 key pair (roundtrip); assert canonicalize is idempotent (serializing the same payload twice yields the same digest); assert the report contains all required fields and `schema_version == "0.9.0"`
- `test_upload_benchmark_report.rs`: local mock HTTP server provides nonce and receives the upload; assert the request contains `schema_version`, `payload_digest`, `signature`, `challenge_nonce`, `client_version`, and artifact files; succeeds when the server returns 202, fails on non-2xx

## Acceptance Criteria

1. Build and tests all pass:

```bash
cd cli/benchmark-probe && cargo build
cd cli/benchmark-probe && cargo test
```

2. Signing roundtrip is covered: after signing with the test key, verification with the corresponding public key succeeds:

```bash
cd cli/benchmark-probe && cargo test --test test_sign_submission_payload
```

3. Artifact digest determinism: the same file bytes yield the same `sha256:<hex>` (with a corresponding assertion).
4. Upload request fields complete: mock server asserts it received `signature`, `payload_digest`, `challenge_nonce`, `client_version`, and artifact files:

```bash
cd cli/benchmark-probe && cargo test --test test_upload_benchmark_report
```

5. On server non-2xx, the CLI exits with a non-zero exit code and outputs an error.

## Notes

- Code, comments, and commit messages must be in English; follow `cargo fmt` and `cargo clippy` (if configured).
- The contract for the upload target `POST /v1/submissions` is defined by S09 (S09 is in W3, earlier than this wave; integration testing can be coordinated).
- Do not make git commits.
