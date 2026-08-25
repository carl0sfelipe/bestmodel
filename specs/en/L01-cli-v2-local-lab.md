# CLI v2 — Local Lab (tune → measure → store → analyze → contribute)

> Phase 1+ story cluster (L01–L07). Language policy: Phase 1 specs are written in
> English. Builds on Phase 0 deliverables S00–S12 (benchmark-probe CLI, ingestion
> pipeline, roofline kernel, trust system, leaderboard).

## Objective

Turn `benchmark-probe` from a single-run measurement probe into a **local lab**:
the CLI that a user's AI agent (or the user) runs to discover the best SOTA model
their machine can run *and* the best engine configuration to run it with. Every lab
session writes a frozen, reproducible experiment record locally, ranks measured vs
predicted results, and — with consent — ships signed, validated runs back to the
shared pool, so the next machine starts its search from better priors.

Positioning (from competitive research, 2026-08): single-machine tuners exist
(llama-optimus, llama-throughput-lab, picchio, ollama-optimizer), but **nobody
combines tuning + measurement + a shared signed pool + calibrated prediction**.
That flywheel is the product.

## Borrowed patterns (provenance)

| Source repo (stars) | Pattern we adopt |
|---|---|
| BrunoArsioli/llama-optimus (42) | Hierarchical search: numerical flags first (batch, ubatch, threads, ngl), categorical second (flash-attn, override-tensor, mmap, kv cache type), then final refinement. Mandatory warmup ("never trust cold-start numbers"), N repeats per trial with mean/std, auto-estimate max `-ngl`, emit ready-to-paste server command, final optimized-vs-default comparison. |
| alexziskind1/llama-throughput-lab (442) | Sweep cells over (parallel × concurrency × instances...); incremental CSV per sweep; an `analyze` step that ranks cells by any field (top-N). |
| logxio/picchio (17) | Evidence honesty checks: detect silent CPU fallback and implausible tok/s claims from engine output. Adopted as intake evidence rules. |
| ggml-org/llama.cpp `llama-bench` | Measurement kernel for kernel-level pp/tg numbers (CSV output), used when a local llama.cpp build is present; optional. |
| Our Phase 0 | Everything else: roofline predictors, signed uploads (contract 0.9.x), anti-fraud worker, trust tiers, leaderboard, catalog + priors. |

## Target user/agent experience

```bash
# 1. What is the best SOTA I can run here, and how should I run it?
benchmark-probe plan            # ranked candidates from pool + predictors (no local run yet)

# 2. Lab session: tune + measure the top candidates on THIS machine
benchmark-probe lab --candidates 3 --trials 20
#    -> sweeps llama.cpp/Ollama knobs, stores experiments/, prints measured-vs-predicted

# 3. Report
benchmark-probe report          # table: config | measured | predicted | delta; best command line

# 4. Contribute (consent-gated; this is the flywheel)
benchmark-probe contribute      # sign + batch-upload validated lab runs
```

Flags relevant to both agent and human consumption: `--json`, `--markdown`,
`--no-upload` (local-only), `--budget <minutes>` (agent-friendly timeboxing),
`--resume` (continue an interrupted lab directory).

## Modules (cli/benchmark-probe)

| Module | Responsibility |
|---|---|
| `plan_candidates.rs` | Call `POST /v1/match/hardware-to-models` + priors endpoint; emit ranked candidate configs (model × quant × runtime × suggested flags). Offline fallback: predictors only. |
| `tuning_search.rs` | Search-space definition + hierarchical search loop (numeric → categorical → refine). Optimizer is pluggable: start with deterministic grid/random baseline (L02), upgrade to TPE/Bayesian (L03). Warmup discipline + repeats built-in. |
| `lab_recorder.rs` | `experiments/<ts-id>/{meta.json,metrics.json,engine.log}` + append-only `index.jsonl` (flat, AI-friendly, one line per cell). Frozen scenario recipes with explicit `recipe_version`. |
| `ollama_tuner.rs` | Ollama knob surface: `num_gpu`, `num_ctx`, `num_batch`, KV cache quant, flash attention, keep/window — measured through `/api/generate` timings. Open competitive lane (no mature OSS equivalent). |
| `report_lab.rs` | measured vs predicted (roofline kernel) delta table; best config; copy-paste `llama-server` / Ollama env commands; `--json`/`--markdown`. |
| `contribute_lab.rs` | Batch-convert lab cells → contract 0.9.1 reports, sign (existing Ed25519 path), upload via existing intake; respect `--no-upload`. |
| `evidence_checks.rs` | picchio-style local honesty checks before upload: CPU-fallback markers in engine logs, tok/s vs roofline ceiling, ttft consistency. Failures become warnings or block upload (configurable). |

## API additions (apps/public-api)

| Endpoint | Purpose |
|---|---|
| `POST /v1/priors/hardware-similar` | Given hardware fingerprint/specs, return tuned configs + measured cells from the closest machines in the pool (k-NN over gpu model/bandwidth/vram/cpu class). Seeds the local search so agents spend trials on refinement, not exploration. |
| `GET /v1/configs/best` | Best known config per (gpu_model, model_release, quant) — "leaderboard of configurations". |
| leaderboard extension | `group_by=config` view; trust-tier badges per config entry. |

## Contract evolution 0.9.0 → 0.9.1 (additive, backward-compatible)

- `statistics` block: `repeats`, `std`, `min`, `max` per metric.
- `tuning` block: `method` (grid/random/tpe), `trials`, `flags` snapshot, `warmup_runs`.
- `spec_decode` block: `enabled`, `method` (draft/ngram/mtp), `k`, `acceptance_pct` — anti-fraud compares spec runs against the correct ceiling.
- `peak_ram_mib` (optional): CPU/hybrid-residency runs.
- `recipe_version` on scenario.

Anti-fraud worker additions: picchio checks; roofline ceiling selection aware of
`spec_decode`; MoE residency rule (full-offload vs active-weights) documented.

## Stories and waves

| Story | Title | Wave |
|---|---|---|
| L01 | Lab recorder + frozen recipes (`experiments/`, `index.jsonl`, versions) | P1-W1 |
| L02 | Scenario sweep runner: llama.cpp via llama-server HTTP; Ollama via /api; `lab` command with grid/random search + warmup + repeats | P1-W1 |
| L03 | Bayesian/TPE optimizer over the sweep space (candidate: embedded TPE or `argmin`-based BO; decide after spike) | P1-W2 |
| L04 | Priors endpoints (`hardware-similar`, `configs/best`) + pool-seeded search in `lab` | P1-W2 |
| L05 | `report` command (measured-vs-predicted, best command lines, markdown/json) | P1-W2 |
| L06 | `contribute` command + contract 0.9.1 + worker extensions (picchio checks, spec-decode ceilings) | P1-W3 |
| L07 | Ollama tuner mode + MCP publication of lab tools (agent distribution layer) | P1-W3 |

Exit criteria (cluster):
1. On a machine with llama.cpp and/or Ollama, `benchmark-probe lab` runs unattended
   within `--budget`, stores a valid `index.jsonl`, and `report` prints best config
   with measured-vs-predicted delta < roofline ceiling.
2. `contribute` uploads lab runs that pass the intake pipeline (validated, not
   quarantined) for at least one honest session on the internal fleet.
3. `lab` seeded by `/v1/priors/hardware-similar` uses fewer trials than unseeded
   random search to reach the same best-known throughput (A/B on one machine).

## Prerequisites / gaps to close first

- Linux topology in `collect_system_topology` (nvidia-smi / lspci / /proc/cpuinfo) —
  without it the fleet fingerprints are empty.
- Roofline threshold calibration decision (0.92 vs measured 0.94 on real QwQ runs;
  lab runs currently quarantined pending this).
- MoE full-offload residency model (active-weights formula under-predicts).

## Open questions

1. Optimizer crate: embedded TPE (small, no deps, fits single-binary ethos) vs
   `argmin` BO. Spike in L03 decides.
2. Should `lab` auto-download models (Ollama pull / HF fetch) or require local
   GGUF paths? Proposal: Ollama auto-pull (built-in), llama.cpp requires path.
3. Consent UX for `contribute`: default opt-in with clear summary of what leaves
   the machine, or opt-out? Proposal: opt-in, first-run prompt, `--no-upload`
   always respected.
