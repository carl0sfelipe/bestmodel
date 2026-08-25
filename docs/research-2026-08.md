# Research Notes — 2026-08 (competitive + tuning tooling)

Rounds 1–2 performed via GitHub search; Round 3 is a live-platform teardown.
Conclusions feed `specs/en/L01-cli-v2-local-lab.md` and `docs/backlog.md`.
Re-check before Phase 1 builds — this landscape moves fast.

## Round 1 — "which model fits my hardware" space

| Repo | Stars | Lang | Takeaway |
|---|---|---|---|
| [Andyyyy64/whichllm](https://github.com/Andyyyy64/whichllm) | ~6.1k | Python | Category leader. One-command answer (`uvx whichllm@latest`), GPU simulation before buying, `plan`/`upgrade` reverse lookups, evidence-graded scores (direct/variant/base/interpolated/self-reported). **But**: speeds are static bandwidth-formula estimates ("planning range, not a live benchmark"); no community measurement pool; read-only. |
| [Wecko-ai/modelfit-hardware-dataset](https://github.com/Wecko-ai/modelfit-hardware-dataset) | ~22 | JS | CC-BY dataset "which Ollama models fit which hardware"; static, no engine, no ingestion. |
| [atulitdewangan/local-llm-hardware-predictor](https://github.com/atulitdewangan/local-llm-hardware-predictor) | 0 | TS | Toy web predictor; validates the idea is being attempted bottom-up. |
| [Merrymak3r/llm-bakeoff](https://github.com/Merrymak3r/llm-bakeoff) | ~1 | Python | Closest in spirit: frozen reproducible bake-off on YOUR machine (quality+speed+VRAM); single-machine, no pool. |

**Gap confirmed**: everyone answers with frozen formulas or third-party
leaderboards; nobody runs a signed, validated, community-measured pool feeding a
calibrated predictor. Positioning: *they have a formula, we have a flywheel.*

**UX to borrow** (spec L01): one-command answer; `plan "model"` reverse lookup;
`upgrade "gpuA" "gpuB"`; `--json`/`--markdown`; pre-buy simulation.

## Round 2 — tuning llama.cpp / Ollama + measure-store-analyze

| Repo | Stars | Lang | What we adopt |
|---|---|---|---|
| [BrunoArsioli/llama-optimus](https://github.com/BrunoArsioli/llama-optimus) | ~42 | Python | **Key reference.** Optuna/TPE over llama.cpp flags (batch, ubatch, threads, ngl, flash-attn, mmap, kv cache type, override-tensor); hierarchical search (numerical → categorical → refine); mandatory warmup ("never trust cold-start numbers"); repeats per trial; auto max-`-ngl` estimate; emits copy-paste `llama-server` + `llama-bench` commands; optimized-vs-default final comparison. Ends with "contribute your configs" — with no pool behind it (our opportunity). |
| [alexziskind1/llama-throughput-lab](https://github.com/alexziskind1/llama-throughput-lab) | ~442 | Python | Sweep cells (threads / parallel × concurrency × instances w/ nginx round-robin); incremental CSV results; `analyze-data.py` ranking any field top-N. Maps 1:1 to our lab recorder + report. |
| [logxio/picchio](https://github.com/logxio/picchio) | ~17 | Python | Detects silent CPU fallback and mislabeled tok/s in llama.cpp/Ollama output (one file, zero deps). Adopt as evidence honesty checks (spec L02/L06). |
| [ikawrakow/ik_llama.cpp](https://github.com/ikawrakow/ik_llama.cpp) | ~3.0k | C++ | What a "tuned fork" looks like (extra quants, faster kernels). Reference only. |
| ggml-org/llama.cpp `llama-bench` | — | C++ | Measurement kernel (CSV); use when a local build exists. |
| [AnkitNayak-dev/llmBench](https://github.com/AnkitNayak-dev/llmBench) | ~45 | Python | Deep runtime benchmarking (methodology notes). |
| [uncSoft/anubis-oss](https://github.com/uncSoft/anubis-oss) | ~198 | Swift | Apple-Silicon local benchmarking. |
| [novitalabs/autotuner](https://github.com/novitalabs/autotuner) | ~13 | Python | Auto-tuning inference engine params per model (concept, cloud-oriented). |
| Ollama tuning | — | — | Lane mostly empty: guides (jameschrisa/Ollama_Tuning_Guide) + embryonic "ollama-optimizer" projects; measuring tools (OMeter, ollama-benchmark) don't tune. Our Ollama tuner (spec L07) has no mature OSS equivalent. |

## Synthesis (drives CLI v2 design)

Nobody combines: tuning + measurement + frozen storage + pool + calibrated
prediction + anti-fraud. CLI v2 = llama-optimus (search discipline) ×
throughput-lab (sweep→CSV→analyze) × picchio (honesty checks) × our Phase 0
(signed pool + predictors + trust). Pool-seeded search (start Bayesian search
from nearest neighbor's best config) is the concrete economy no competitor has.

## Round 3 — live competitor teardown: localmaxxing.com (2026-08-12)

First live platform found in our lane (Rounds 1–2 were GitHub repos only).
Community speed-test leaderboard for local LLM inference. Scale as of today:
~2,029 users, ~5,021 runs, 262 hardware entries, 687 models cataloged, 484
quality-benchmark runs. Surfaces: CLI + web form + agent-first API
(`/api/agent-context` metadata endpoint, `dry-run` validation, OpenAPI 3.1),
community quality benchmarks (GSM8K/HellaSwag/HumanEval+/ARC, admin-approved),
hardware marketplace with "speed-test-backed" listings, rentals, Pro tier,
on-site ads, 18 languages, strong educational get-started content.

**Overlap with our plan**: they are essentially our Phase 1 (community
leaderboard) executed and live — they already exceed our Phase-1 exit criteria
(1000+ runs, 100+ submitters). Their `engineFlags` capture (commandSnippet,
spec-decoding/MTP, kv dtype, offload) is close to L01's config coverage.
Marketplace (our Phase 3 item) is validated by them.

**What they lack — the gap that is our core thesis**:

1. **No matching/decision engine.** No hardware→models or model→hardware
   query anywhere (site or API). Users browse leaderboards manually; nothing
   answers "can *my* machine run X, how fast, at which quant/context".
2. **No calibrated prediction.** Their "decode calculator" is an explicit
   *theoretical upper-bound* tool with manual inputs, disconnected from their
   own 5k-run pool (pool data only sorts hardware presets). They even teach
   the roofline rule in prose but never operationalize it into per-user
   predictions with measured error bars (our VRAM P50 6.18%).
3. **Shallow trust.** Submissions are self-reported JSON over an API key;
   response shows `status: APPROVED` immediately; no signatures, no
   artifacts/evidence, no plausibility validation. "Verified" filters refer
   to *user identity*, not runs. Anti-abuse = 1 submission/min rate limit.
4. **No ROI layer.** Static cost ballparks in an article; no local-vs-API
   decision tooling.
5. **No tuning loop.** engineFlags are recorded, never recommended;
   pool-seeded search (L01) remains uncontested.

**Threat read (honest)**: they own the ingredient we lack — an active
community pool with distribution and an agent-first ingestion funnel. They are
one modeling project away from closing the predictor gap, *except* their pool
is uncurated self-reports; calibrating on it is garbage-in. Our signed +
validated pool is the defensible input for the predictor. Backlog implication:
track C head-on leaderboard virality now competes with an incumbent; the wedge
is track A (lab/tuner) + track B (their whole pool is effectively our B2
"claimed track" without B3 voting/priors) + the decision engine. C4 SEO pages
(hardware × model with predictions) stay differentiated — they have no
per-combo prediction pages.

**Ideas to borrow**: `/api/agent-context` one-call agent onboarding; `dry-run`
submission validation endpoint; saved setups that prefill submissions; fuzzy
model-name → canonical HF id resolution endpoint; purchase-record fields on
runs feeding cost/perf tables; reaction emojis on runs.
