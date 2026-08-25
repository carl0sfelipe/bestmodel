# Findings & Calibrations

Numbered findings from real-world data and integration. Open decisions are flagged
with their backlog id. Cite these (e.g. "per F2") in specs/PRs instead of
re-deriving them.

## F1 — VRAM prediction validated on real hardware (CLOSED)

Plan §11.2 formulas measured at **P50 6.18%** error on RTX 3090 (QwQ-32B Q4_K_M,
ctx 4k/8k), within the Phase 0 exit criterion (<10%). Live harness:
`tests/regression/vram_error_harness.py` — extend the corpus with every new
measured machine; never delete entries.

## F2 — Roofline ceiling vs anti-fraud threshold (OPEN — backlog A5)

An honest QwQ-32B run reaches **94%** of our roofline estimate (36.8 vs
39.2 tok/s), above the S10 quarantine threshold of **0.92** — the anti-fraud
rule would quarantine legitimate runs. The lab's QwQ runs are quarantined in the
DB pending this decision. Options: raise threshold to ~0.97, or tighten
U_RUNTIME/U_QUANT so the ceiling itself drops. Decide with more machines' data.

## F3 — MoE decode sits far below roofline (OPEN — model refinement)

Qwen3.5-35B-A3B measured 140.5 tok/s ≈ **33%** of roofline. The decode roofline
(§11.3) is an optimistic ceiling for MoE on llama.cpp (expert routing +
non-contiguous reads). Not an anti-fraud issue (no false positives), but match
endpoint `expected_decode_tok_s` over-promises for MoE. Needs a per-architecture
efficiency factor in a later kernel iteration.

## F4 — Speculative decoding breaks the decode roofline (OPEN — contract 0.9.1)

Spec-decode runs (n-gram/draft/MTP) can exceed the 1-token/step roofline
(lab: +64% with n-gram on QwQ). Anti-fraud must know `spec_decode` context to
pick the right ceiling; contract 0.9.1 gets a `spec_decode` block (spec L06).

## F5 — Hybrid linear-attention KV over-estimated (OPEN — kernel gap)

Qwen3.5-style models (linear_attention + full_attention layers) don't accumulate
KV on linear layers; our KV formula treats all 40 layers as full-attention and
overestimates context cost. Kernel extension deferred; document per-model when it
matters.

## F6 — Duration rule = throughput consistency, not absolute floor (CLOSED)

Original absolute 10s floor rejected legitimate fast runs (512 tokens at
140 tok/s ≈ 3.7s). Rule now: `duration ≥ max(1.0, 0.5 × generated_tokens /
decode_tok_s)` (`validate_submission_payload.py`).

## F7 — CPU/hybrid runs have no first-class home (OPEN — backlog/contract 0.9.1)

Contract 0.9.0 requires `peak_vram_mib > 0` and the feasibility engine models VRAM
only. CPU-RAM inference (lab: DeepSeek-V4-Flash 162GB on 1TB DDR4 @ 2.93 tok/s)
needs `peak_ram_mib`, a cpu_model seed, and a RAM roofline. Tracked for 0.9.1.

## F8 — Integration-only bugs (all fixed; lessons)

- jsonb inserts need `psycopg.types.json.Json` (internal finding log B2).
- NUMERIC → Decimal → coerce to float before math (B3).
- Redis stream keys/values are bytes — decode before dict-key use (B4).
- PKCS8 v1 PEM for cross-language Ed25519 keys (B1/D6).
Lesson: unit tests with fakes don't exercise serialization boundaries; the gate
exists precisely to catch this class. Keep `make gate` green on every merge.
