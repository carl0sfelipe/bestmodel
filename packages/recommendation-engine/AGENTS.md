# packages/recommendation-engine — Map

Ranking layer (plan §11.10 balanced mode; cost/latency modes deferred).

| Module | Content |
|---|---|
| `filter_feasible_models.py` | feasibility first (§11.1): peak ≤ capacity × 0.95; unknown capacity passes through |
| `calculate_ranking_score.py` | weights {decode .30, prefill .20, context .15, quality .15, energy .10, trust .10}; `robust_min_max` (p95==p5 → 1.0); infeasible → score 0 |

Consumers: `apps/public-api` leaderboard service. Energy uses decode/power
(zero power → 0 — documented gap until power data exists). Percentile =
linear interpolation over the feasible cohort.

## Change checklist

- Touched SAFETY_MARGIN or the ranking formula? Same commit: the filters
  suite (feasibility demos pin the 95% margin), the e2e leaderboard
  assertions, and the LOAD-BEARING comment at the constant's site.
- New entry field consumed here? It must come from the derived leaderboard
  row (fake derives it too — S26), never from a canned test value.

## Load-bearing decisions

- SAFETY_MARGIN = 0.95 (plan §11.2): peak must fit within 95% of capacity;
  infeasible rows are hidden and rank-zeroed. Changing it reclassifies
  every leaderboard row — product decision, not a tweak.
