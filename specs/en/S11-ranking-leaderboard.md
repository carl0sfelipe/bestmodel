# S11: Recommendation engine ranking score and leaderboard filtering (ranking + leaderboard)

## Goal

In `packages/recommendation-engine` (Section 15 directory structure of the plan), implement the balanced-mode composite ranking score (Section 11.10 formula), p5/p95 robust normalization, and infeasible-zeroing; extend `apps/public-api`'s `GET /v1/leaderboard` to support filtering by hardware/model/runtime/quant/context and output rankings.

## Dependencies

- S10 (validated / quarantined benchmark runs with `trust_assessment` persisted, as ranking input)

## Wave

W5

## Deliverables

| Path | Description |
|---|---|
| `packages/recommendation-engine/pyproject.toml` | Package configuration (depends on roofline-kernel, domain-schema) |
| `packages/recommendation-engine/src/filter_feasible_models.py` | Feasibility filtering (Section 11.1: feasibility first, then ranking) |
| `packages/recommendation-engine/src/calculate_ranking_score.py` | Balanced formula + `robust_min_max` normalization + infeasible-zeroing |
| `packages/recommendation-engine/tests/test_calculate_ranking_score.py` | Ranking score unit tests |
| `packages/recommendation-engine/tests/test_filter_feasible_models.py` | Feasibility filtering unit tests |
| `apps/public-api/src/routes/leaderboard_route.py` | Add filter query parameters |
| `apps/public-api/src/services/query_leaderboard.py` | Filtering and sorting by `rank_score` implementation |
| `apps/public-api/tests/test_leaderboard_filters.py` | Leaderboard filter tests (test data) |

## Technical Requirements

Reference Section 11.1 (from the original internal design doc) (design principles), Section 11.10 (composite ranking formula), Section 12.5 (Trust Levels ranking weights).

### balanced ranking formula (11.10)

\[
Score = 0.30 \times DecodeScore + 0.20 \times PrefillScore + 0.15 \times ContextCapacityScore + 0.15 \times QualityRetentionScore + 0.10 \times EnergyEfficiencyScore + 0.10 \times TrustScore
\]

Sub-score definitions:

- `DecodeScore = robust_min_max(decode_tok_s, p5, p95)`
- `PrefillScore = robust_min_max(prefill_tok_s, p5, p95)`
- `ContextCapacityScore = robust_min_max(max_context_tokens, p5, p95)`
- `QualityRetentionScore = robust_min_max(quality_retention_estimate, p5, p95)`
- `EnergyEfficiencyScore = robust_min_max(decode_tok_s / power_watt_avg, p5, p95)` (higher is better)
- `TrustScore = robust_min_max(trust_score, p5, p95)`

### Robust normalization (11.10)

\[
Score_{normalized} = robust\_min\_max(value, p5, p95) = clamp\left(\frac{value - p5}{p95 - p5}, 0, 1\right)
\]

- `p5` / `p95` are computed per dimension within the candidate set
- When `p95 == p5` (no dispersion), return `1.0`

### Infeasible-zeroing (11.10)

```text
if peak_vram > usable_vram:
    feasible = false
    rank_score = 0
```

`filter_feasible_models.py` handles feasibility determination (reusing Section 11.2 `VRAM_peak ≤ VRAM_capacity × 0.95`); after filtering, items with `feasible=false` are hidden and `rank_score` is set to 0.

### leaderboard filtering

`GET /v1/leaderboard` adds filter parameters (ranking only `status='validated'` runs):

- `gpu_model_id` (hardware)
- `model_release_id` (model)
- `runtime_engine` (runtime)
- `quantization_profile_id` / `quant_format` (quant)
- `context_tokens` (context: `context_tokens_min` / `context_tokens_max`)
- `batch_size` (optional)
- `sort` (default `rank_score` descending)

`query_leaderboard.py` assembles the filter conditions, calls `calculate_ranking_score` to compute and sort, and returns entries containing `rank_score`, `feasible`, each metric, and `trust_score`.

### Tests

- `test_calculate_ranking_score.py`: construct a candidate set; assert scores in `[0,1]`, higher values yield higher scores, `feasible=false` gives `rank_score == 0`, and `p95==p5` normalizes to `1.0`
- `test_leaderboard_filters.py`: seed the test database with validated runs of 2 models × 2 GPUs, verify each filter parameter and combined filtering return only matching items, sorted by `rank_score` descending

## Acceptance Criteria

1. Unit tests all green:

```bash
uv run pytest packages/recommendation-engine -v
```

2. Leaderboard route tests all green (including filtering):

```bash
uv run pytest apps/public-api -q
```

3. Infeasible items: `feasible=false` must give `rank_score == 0` (with a corresponding assertion).
4. Normalization bounds: `robust_min_max` output is clamped to `[0,1]`; `p95==p5` returns `1.0`.
5. Leaderboard filter correctness: on seeded data, `?model_release_id=X` returns only X's runs, the combined filter `?gpu_model_id=Y&runtime_engine=llama_cpp` likewise returns only matching items, and sorting is `rank_score` descending.

## Notes

- Code, comments, and commit messages must be in English; functions 4–20 lines, single file < 500 lines.
- cost-sensitive and latency-sensitive modes (11.10) and ROI priority (`prioritize_roi_mode`) are out of scope for this wave.
- Do not make git commits.
