# S09: Public query API and submission entry point (public-api)

## Goal

Implement `apps/public-api` (FastAPI + Pydantic v2) as the external REST/JSON API (Section 15 directory structure of the plan): `POST /v1/match/hardware-to-models` and `POST /v1/match/model-to-hardware` (Section 9.4 contract), `GET /v1/leaderboard` (basic version), `POST /v1/submissions` (intake: schema validation + deduplication + enqueue). All external services (database sessions, artifact vault, Redis queue) are injected through providers (Section 14 engineering decision 11); tests use fake-adapters (decision 13).

## Dependencies

- S04 (`packages/roofline-kernel` VRAM / context feasibility kernel: `estimate_vram_footprint`, `estimate_context_limit`, used for computing feasibility and `max_context_tokens` in match)
- S02 (PostgreSQL migration: `benchmark_run`, `benchmark_artifact`, etc. tables and `benchmark_run_lookup_idx`)

## Wave

W3

## Deliverables

| Path | Description |
|---|---|
| `apps/public-api/pyproject.toml` | Package configuration (FastAPI, Pydantic v2, uvicorn, psycopg/SQLAlchemy, etc.) |
| `apps/public-api/src/main.py` | FastAPI application entry point, registers routes and dependency providers |
| `apps/public-api/src/routes/hardware_match_route.py` | `POST /v1/match/hardware-to-models` |
| `apps/public-api/src/routes/model_match_route.py` | `POST /v1/match/model-to-hardware` |
| `apps/public-api/src/routes/benchmark_submission_route.py` | `POST /v1/submissions` and `GET /v1/submissions/nonce` |
| `apps/public-api/src/routes/leaderboard_route.py` | `GET /v1/leaderboard` (basic version) |
| `apps/public-api/src/schemas/hardware_match_request.py` | hardware-to-models request model (Pydantic v2) |
| `apps/public-api/src/schemas/model_match_request.py` | model-to-hardware request model |
| `apps/public-api/src/schemas/benchmark_submission_schema.py` | submission request model (aligned with S01 contract 0.9.0) |
| `apps/public-api/src/services/submit_benchmark_run.py` | intake service: validate, verify signature, deduplicate, persist, store artifacts, enqueue |
| `apps/public-api/src/services/query_hardware_match.py` | hardware-to-models match query |
| `apps/public-api/src/services/query_model_match.py` | model-to-hardware match query |
| `apps/public-api/src/services/query_leaderboard.py` | leaderboard basic query |
| `apps/public-api/src/dependencies/database_session_provider.py` | database session provider (FastAPI `Depends`) |
| `apps/public-api/src/dependencies/artifact_vault_provider.py` | artifact vault provider |
| `apps/public-api/tests/` | pytest unit and route tests (using fake-adapters and a test database) |

## Technical Requirements

Reference Section 9.4 (from the original internal design doc) (frontend/backend interaction), Section 10 (entities and schemas), Section 14 engineering decisions (DI, fake-adapters), Section 15 (`apps/public-api` directory structure).

### hardware-to-models (9.4)

`POST /v1/match/hardware-to-models`; request and response fields are verbatim consistent with the example in Section 9.4:

- Request: `gpu_model_ids`, `gpu_count`, `ram_gib`, `os_name`, `target_model_family`, `target_context_tokens`, `priority`
- Response: `matches` array, each item containing `model_release_id`, `quantization_profile_id`, `runtime_id`, `feasible`, `expected_decode_tok_s`, `expected_prefill_tok_s`, `expected_ttft_ms_8k_prompt`, `expected_peak_vram_gib`, `max_context_tokens`, `quality_retention_estimate`, `trust_score`
- Feasibility determination and `max_context_tokens` call the S04 kernel (`VRAM_peak ≤ VRAM_capacity × 0.95`, Section 11.2)

### model-to-hardware

`POST /v1/match/model-to-hardware`:

- Request: `model_release_id`, `target_context_tokens`, `batch_size`, `priority`
- Response: `configs` array, tagged by role (`minimum` / `recommended` / `cost_efficient`), each item containing `gpu_model_id`, `gpu_count`, `quantization_profile_id`, `runtime_id`, `feasible`, `expected_peak_vram_gib`, `expected_decode_tok_s`, `expected_prefill_tok_s`, `max_context_tokens`
- Covers Section 14 PRD Flow 2 (Model → Hardware: minimum runnable / recommended / cost-efficient configurations)

### leaderboard basic version

`GET /v1/leaderboard`: return benchmark runs with `status='validated'` (sorted by submission time descending, basic pagination). Full filtering (hardware/model/runtime/quant/context) is provided by S11.

### submissions intake (9.2 module: submission-intake)

`POST /v1/submissions` receives `multipart/form-data`:

- `report`: 0.9.0 report JSON string (including `artifacts[].artifact_kind` and `artifacts[].sha256`)
- `signature`, `payload_digest`, `challenge_nonce`, `client_version`
- artifact files: named `artifact_0`, `artifact_1`, …

Processing flow:

1. Schema validation: `report` must pass the S01 contract 0.9.0 (Pydantic model), otherwise return 400 with error details
2. `payload_digest` must equal `SHA256(canonicalized(report))`, otherwise return 400
3. Signature verification: `signature` must verify against the local Ed25519 public key, otherwise return 400 (Section 12.6 "invalid signature must be rejected"). Phase 0 has no account/key registration; verification uses a trusted public key configured via env (e.g., `TRUSTED_ED25519_PUBLIC_KEY_PATH`); per-account registered keys belong to Phase 1.
4. Artifact validation: the SHA-256 of each uploaded file must match `report.artifacts[].sha256`, and files are stored via the `artifact_vault` provider
5. Deduplication: query for existing records by the five dimensions of `benchmark_run_lookup_idx` (`hardware_submission_id`, `model_release_id`, `quantization_profile_id`, `inference_runtime_id`, `benchmark_scenario_id`); if present, return 409
6. Persist: insert `benchmark_run` (`status='submitted'`), `benchmark_metric`, `benchmark_artifact`
7. Enqueue: push event to Redis Streams for the S10 worker to consume (Section 14 decision 8: queue-based async validation); return 202 with `run_id`

`GET /v1/submissions/nonce`: return `{ "challenge_nonce": "<uuid>" }` for the CLI to request before running (Section 12.1 step 1).

### DI and isolation (Section 14 decisions 11, 13)

- `database_session_provider.py` and `artifact_vault_provider.py` are injected via FastAPI `Depends`
- Tests use `packages/fake-adapters` (fake database, fake artifact vault, fake Redis), without depending on real external services

## Acceptance Criteria

1. Unit and route tests all green:

```bash
uv run pytest apps/public-api -v
```

2. After infrastructure is up, uvicorn starts normally:

```bash
docker compose -f infra/docker/docker-compose.yml up -d postgres redis
cd apps/public-api && uvicorn src.main:app --host 0.0.0.0 --port 8000
```

3. hardware-to-models returns matches conforming to the Section 9.4 contract:

```bash
curl -s -X POST http://localhost:8000/v1/match/hardware-to-models \
  -H 'Content-Type: application/json' \
  -d '{"gpu_model_ids":["gpu-rtx-4090-24gb"],"gpu_count":2,"ram_gib":96,"os_name":"ubuntu-22.04","target_model_family":"qwen-2.5-coder","target_context_tokens":32768,"priority":"balanced"}'
```

   The response contains a `matches` array, and the fields match the Section 9.4 example.

4. A valid submission returns 202 and `run_id` exists; duplicate submission returns 409; invalid schema returns 400 (with error details); payload digest mismatch returns 400.
5. `GET /v1/leaderboard` returns 200 and the list of persisted runs.

## Notes

- Code, comments, and commit messages must be in English; single files no more than 500 lines, functions kept at 4–20 lines (Section 15 engineering norms).
- Full leaderboard filtering and ranking scores belong to S11; evidence parsing after signature verification, roofline plausibility checks, and z-score belong to S10.
- Do not make git commits.
