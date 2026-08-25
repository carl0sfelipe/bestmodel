# S12: Phase 0 exit integration gate (end-to-end gate)

## Goal

As the Phase 0 (Section 7) exit gate: bring up the full stack with `docker compose`; verify the end-to-end flow `CLI → sign → intake → validation → leaderboard` works; verify the Section 7 exit criteria command by command (10 internal machines can run the standardized benchmark, 50 models × 20 GPUs of seed data are queryable, VRAM prediction error P50 < 10%); `make test` all green. Deliver end-to-end tests, a VRAM error harness, and a command-by-command checklist.

## Dependencies

- S00–S11 (all complete)

## Wave

W6

## Deliverables

| Path | Description |
|---|---|
| `tests/integration/test_e2e_submission_flow.py` | End-to-end flow test: CLI generates signed report → `POST /v1/submissions` → worker validates → `GET /v1/leaderboard` shows the validated run |
| `tests/regression/test_vram_error_harness.py` | VRAM prediction error P50 metric test (target < 10%) |
| `tests/regression/vram_error_harness.py` | VRAM error harness: compute prediction errors over the regression corpus and output P50 |
| `infra/scripts/e2e_gate.sh` | Gate script: compose up → migrate → seed → build CLI → end-to-end walkthrough → print checklist |
| `Makefile` | Add target `gate` (depends on `test`, `migrate`, `seed`) |

## Technical Requirements

Reference Section 7 (from the original internal design doc) (Phase 0 exit criteria), Section 15 (engineering norms landing: `make test`), Section 9.3 (CLI output), Section 12.1 (signed upload).

### End-to-end flow (e2e_gate.sh)

Execute in order:

1. `docker compose -f infra/docker/docker-compose.yml up -d` (postgres, redis, minio, etc.)
2. `make migrate` (exit code 0)
3. `make seed` (exit code 0)
4. `make test` (cargo test + `uv run pytest` all green)
5. `cd cli/benchmark-probe && cargo build`
6. Generate signed report: run `benchmark-probe` with mock runtime, producing `report.json` and the signature file
7. Start the API: `cd apps/public-api && uvicorn src.main:app --port 8000`
8. Start the worker: `cd apps/intake-worker && uv run python -m src.worker`
9. Upload: `curl -X POST http://localhost:8000/v1/submissions -F report=@report.json -F signature=... -F payload_digest=... -F challenge_nonce=... -F client_version=... -F artifact_0=@...`
10. Query: `curl http://localhost:8000/v1/leaderboard` must include that `run_id` with `status='validated'`

### VRAM error harness (exit criterion: P50 < 10%)

- Use a regression corpus: measured `(measured_peak_vram_gib, hardware/model/quant/scenario)` pairs (fixture or seed data)
- Predicted values are computed by roofline-kernel `estimate_vram_footprint`
- Per-sample relative error `abs((predicted − measured) / measured) × 100%`
- Output and assert error P50 < 10% (Section 7 exit criterion)

### 10 internal machines (exit criterion)

Each internal machine runs the same command and must assert exit code 0 and report generation:

```bash
cd cli/benchmark-probe && cargo run -- --runtime mock --output benchmark-report.json
```

The checklist lists this command; the gate script prints per-machine results.

### 50 models × 20 GPUs queryable (exit criterion)

```bash
psql "$DATABASE_URL" -Atc "SELECT count(*) FROM gpu_model;"     # >= 20
psql "$DATABASE_URL" -Atc "SELECT count(*) FROM model_release;" # >= 50
```

And run one cross query to verify combinational queryability (e.g., a `model_release × gpu_model` join query returns non-empty).

## Acceptance Criteria (command-by-command checklist)

1. Infrastructure and data:

```bash
docker compose -f infra/docker/docker-compose.yml up -d
docker compose -f infra/docker/docker-compose.yml ps                 # all healthy
make migrate                                                          # exit 0
make seed                                                             # exit 0
psql "$DATABASE_URL" -Atc "SELECT count(*) FROM gpu_model;"           # >= 20
psql "$DATABASE_URL" -Atc "SELECT count(*) FROM model_release;"       # >= 50
```

2. Tests all green:

```bash
make test                                                             # cargo + pytest all green
```

3. End-to-end flow (one-click via script):

```bash
bash infra/scripts/e2e_gate.sh                                       # exit 0, prints checklist
```

   Or manually step by step: build CLI → generate signed report → start API → start worker → upload → leaderboard query; the leaderboard response includes the corresponding `run_id` with `status='validated'`.

4. VRAM error gate:

```bash
uv run python -m tests.regression.vram_error_harness                 # prints P50; asserts P50 < 10%
uv run pytest tests/regression/test_vram_error_harness.py -v         # all green
```

5. 10 internal machines: each runs

```bash
cd cli/benchmark-probe && cargo run -- --runtime mock --output benchmark-report.json
```

   Exit code 0 and generates `benchmark-report.json`.

6. `make gate` passes in one click (depends on test/migrate/seed and runs the e2e script).

## Notes

- Code, comments, and commit messages must be in English.
- This wave focuses on verification and integration; apart from tests / harness / gate scripts, no new business code; if the end-to-end walkthrough exposes defects, fix them minimally within the corresponding story modules.
- Do not make git commits.
