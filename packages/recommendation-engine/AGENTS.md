# packages/recommendation-engine — Map

Ranking layer (plan §11.10 balanced mode; cost/latency modes deferred).

| Module | Content |
|---|---|
| `filter_feasible_models.py` | feasibility first (§11.1): peak ≤ capacity × 0.95; unknown capacity passes through |
| `calculate_ranking_score.py` | weights {decode .30, prefill .20, context .15, quality .15, energy .10, trust .10}; `robust_min_max` (p95==p5 → 1.0); infeasible → score 0 |

Consumers: `apps/public-api` leaderboard service. Energy uses decode/power
(zero power → 0 — documented gap until power data exists). Percentile =
linear interpolation over the feasible cohort.
