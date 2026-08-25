# S10: intake worker validation pipeline (validation / evidence / roofline plausibility / deduplication / z-score)

## Goal

Implement `apps/intake-worker` (Python worker, consuming the Redis Streams queue, Section 15 `apps/intake-worker`), consuming submission events enqueued by S09 and executing the Section 12 validation pipeline of the plan: `validate_submission_payload` (signature and field validation, 12.6), `extract_runtime_evidence` (evidence parsing and consistency, 12.2), roofline plausibility check (12.3), duplicate detection and robust z-score (12.4), update status and write `trust_assessment`, and finally `publish_ranking_update` to notify the leaderboard.

## Dependencies

- S09 (`apps/public-api`: intake validation, persistence, and Redis Streams enqueue)
- S05 (`packages/roofline-kernel` `estimate_decode_tokens_per_second`, used to compute `Decode_roofline`)

## Wave

W4

## Deliverables

| Path | Description |
|---|---|
| `apps/intake-worker/pyproject.toml` | Package configuration (redis, pydantic, etc.) |
| `apps/intake-worker/src/worker.py` | Main loop: subscribe to Redis Stream, run pipeline per item |
| `apps/intake-worker/src/validate_submission_payload.py` | Signature verification, schema version, field completeness (12.6 must-reject items) |
| `apps/intake-worker/src/extract_runtime_evidence.py` | Parse artifacts (stdout/config/smi), validate metrics consistent with evidence (12.2) |
| `apps/intake-worker/src/check_roofline_plausibility.py` | 12.3 Decode roofline check → `roofline_violation` |
| `apps/intake-worker/src/check_memory_plausibility.py` | 12.3 VRAM lower bound check → `impossible_memory_footprint` |
| `apps/intake-worker/src/detect_duplicate_submission.py` | 12.4 dimension-group deduplication detection |
| `apps/intake-worker/src/calculate_modified_zscore.py` | 12.4 MAD robust z-score |
| `apps/intake-worker/src/calculate_trust_assessment.py` | Aggregate sub-scores and write `trust_assessment` (11.9 sub-score dimensions) |
| `apps/intake-worker/src/publish_ranking_update.py` | Publish ranking update notification after validation completes |
| `apps/intake-worker/tests/fixtures/valid_run.json` | Valid run fixture |
| `apps/intake-worker/tests/fixtures/fraudulent_run.json` | Fraudulent run fixture (above roofline, VRAM below lower bound, etc.) |
| `apps/intake-worker/tests/test_validate_submission_payload.py` | Validation pipeline unit tests |
| `apps/intake-worker/tests/test_check_roofline_plausibility.py` | Roofline / VRAM check tests |
| `apps/intake-worker/tests/test_calculate_modified_zscore.py` | z-score tests |
| `apps/intake-worker/tests/test_worker_pipeline.py` | End-to-end pipeline tests (valid and fraudulent runs) |

## Technical Requirements

Reference Section 12.2 (from the original internal design doc) (Evidence types), Section 12.3 (Roofline plausibility check), Section 12.4 (statistical anomaly filtering), Section 12.6 (Anti-Fraud rules), Section 11.9 (Trust Score).

### Pipeline (worker.py)

For each enqueued event, execute in order:

1. `validate_submission_payload`
2. `extract_runtime_evidence`
3. `check_roofline_plausibility` + `check_memory_plausibility`
4. `detect_duplicate_submission`
5. `calculate_modified_zscore` (computed against existing runs in the same group)
6. `calculate_trust_assessment` (write `trust_assessment`, including `outlier_flags`)
7. `publish_ranking_update`

Status transitions: `submitted → validated` / `quarantined` / `rejected` (corresponding to the `benchmark_status` enum).

### validate_submission_payload (12.6 must-reject items)

`status='rejected'` if any condition is met:

- invalid signature
- schema version not `0.9.0`
- missing runtime version
- hardware fingerprint clearly contradictory with metrics
- decode exceeding physical limits (merged with the 12.3 roofline check)
- peak VRAM lower than minimum weights footprint (merged with the 12.3 VRAM check)
- benchmark duration too short (below the scenario minimum threshold)
- artifact hash does not match `report.artifacts[].sha256`

### extract_runtime_evidence (12.2)

Parse artifacts such as `runtime_stdout` / `runtime_config` / `gpu_smi_trace`, validating that `ttft_ms`, `prefill_tok_s`, `decode_tok_s`, `peak_vram_mib` are consistent with the log evidence; give a clear error when key evidence is missing.

### Roofline plausibility check (12.3)

\[
Decode_{roofline} = \frac{BW_{eff}}{W_{active} + K_{token} \times S}
\]

- `Decode_roofline` is computed by S05's `estimate_decode_tokens_per_second(hardware, model, quant, scenario)` (the roofline model itself; 12.3 and 11.3 use the same formula)
- If `decode_reported > 0.92 × Decode_roofline` → `outlier_flag = "roofline_violation"`
- If `peak_vram_mib_reported < 0.80 × estimate_vram_footprint(...).peak_vram_bytes / 1048576` (minimum VRAM footprint, computed by roofline-kernel) → `outlier_flag = "impossible_memory_footprint"`
- If either flag is hit, the submission enters `quarantined` (Section 12.5 quarantine review tier)

### Duplicate detection (12.4 dimension groups)

The same dimension group is treated as the same submission: `hardware_model_id`, `model_release_id`, `quantization_profile_id`, `runtime_engine`, `context_tokens`, `batch_size`. If a run with `validated` or `quarantined` status already exists in that dimension group → mark as duplicate and reject.

### Robust z-score (12.4)

Compute over metrics within the same dimension group (e.g., `decode_tok_s`):

\[
MAD = median(|x_i - median(x)|)
\]

\[
ModifiedZ = 0.6745 \times \frac{x_i - median(x)}{MAD}
\]

- `abs(ModifiedZ) > 3.5` → `quarantine_submission()` (status `quarantined`, `outlier_flag = "statistical_outlier"`)
- When `MAD == 0` (insufficient samples or fully identical), skip z-score and do not apply statistical quarantine

### publish_ranking_update

After validation completes, publish an update notification to leaderboard subscribers (run_id, status, `trust_score`). Full ranking recomputation belongs to S11.

## Acceptance Criteria

1. All tests pass:

```bash
uv run pytest apps/intake-worker -v
```

2. Valid run fixture: final `status='validated'`, `outlier_flags` empty, `trust_assessment` written (each sub-score in `[0,1]`).
3. Fraudulent run fixture is handled correctly:
   - `decode_reported > 0.92 × Decode_roofline` → hits `roofline_violation` (with a corresponding unit test assertion)
   - `peak_vram_mib_reported < 0.80 × VRAM_min` → hits `impossible_memory_footprint`
   - invalid signature / invalid schema version / artifact hash mismatch → `status='rejected'`
   - duplicate submission in same dimension group → rejected
   - `abs(ModifiedZ) > 3.5` within same dimension group → `status='quarantined'`
4. `make test` triggers this worker's tests (through the root-level uv workspace).

## Notes

- Code, comments, and commit messages must be in English; functions 4–20 lines, single file < 500 lines.
- Minimum VRAM footprint computation reuses roofline-kernel's `estimate_vram_footprint` (S04 deliverable, already available in W2).
- Leaderboard filtering and ranking score computation belong to S11; do not make git commits.
