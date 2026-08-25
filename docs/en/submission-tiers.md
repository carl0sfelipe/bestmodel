# Submission Tier Design (Two-Tier Report)

> Product direction (confirmed by the user): the platform must support **advanced-player-grade full submissions**, while keeping a
> **zero-friction user-friendly path**. The complexity stays in our collection agent, not passed on to the user.

## Two-Tier Breakdown

| Tier | Users | Submission contents |
|---|---|---|
| Friendly (default) | Regular users | One command: the CLI automatically collects topology, scenario metrics, and stdout, then signs and uploads automatically |
| Advanced | Labs / enthusiasts / datacenters | Full evidence: repeat statistics (mean/std/min/max), spec decode parameters and acceptance rate, RAM usage, nvidia-smi trace, runtime config, quality evaluation (pass@1), etc. |

## Contract Gaps (0.9.0 → 0.9.1 Evolution Checklist)

Using the user's 3090 lab (llm_lab_export.zip) as the reference sample, the current 0.9.0 contract lacks:

1. `statistics` block: repeats / std / min / max (the DB-side benchmark_metric already has p50/p90 columns, but the contract does not expose them)
2. `spec_decode` block: enabled / method(draft/ngram/mtp) / k / acceptance_pct — without it, anti-fraud would compare speculative decoding runs against the wrong roofline
3. `peak_ram_mib` (the metric_kind enum already has it, but the contract and BenchmarkMetrics do not include it; the dominant resource for CPU/hybrid inference)
4. CPU feasibility path: the engine only models VRAM (11.2) and has no RAM/CPU roofline; cpu_model has no seed data
5. KV modeling for hybrid attention models (e.g., Qwen3.5-35B-A3B: linear + full layers) overestimates context usage

## Calibration Items Verified by Real Lab Data

- VRAM prediction error 6.2% (QwQ-32B Q4, passes the <10% criterion)
- Real runs reach 94% of the roofline estimate, which is above the 0.92 threshold → the threshold/efficiency constants need calibration (to be finalized before S12)
- The duration check has been changed from an "absolute 10s floor" to a "consistency with throughput" validation (already implemented)
