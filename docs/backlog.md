# Backlog

Canonical backlog for post-Phase-0 work. Items are grouped by track; ids are
stable and referenced from specs and discussions.

## Track A — CLI v2 Local Lab (spec: specs/en/L01-cli-v2-local-lab.md)

Open questions from the L01 spec (need a decision before/during build):

- **A1 — Optimizer choice.** Embedded TPE (zero-dep, single-binary ethos) vs
  `argmin`-based Bayesian optimization. Decide via L03 spike.
- **A2 — Model acquisition.** Should `lab` auto-pull models (Ollama built-in,
  llama.cpp requires local GGUF path)? Proposal: Ollama auto, llama.cpp manual.
- **A3 — Contribute consent.** Opt-in with first-run prompt + always-honored
  `--no-upload`. Confirm default direction.
- **A4 — Linux topology collection** (prerequisite): nvidia-smi/lspci/procfs in
  `collect_system_topology`; without it fleet fingerprints are empty.
- **A5 — Roofline threshold calibration**: 0.92 rule vs measured 0.94 on real
  QwQ-32B runs (lab runs quarantined pending decision).
- **A6 — MoE residency model**: full-offload footprint vs active-weights formula.

## Track B — Two-tier reporting: verified + claimed

Direction (owner decision): verification is OPTIONAL. Both tracks coexist;
incentives pull users up the track, they never block entry.

- **B1 — Verified track (built in Phase 0)**: CLI-signed runs, artifacts,
  anti-fraud validation, trust score. High leaderboard weight. Incentives:
  contributor reputation/tiers (extend trust levels L0–L4 to humans), badges,
  priority placement, bounty points for settling disputed claims (B3).
- **B2 — Claimed track (new)**: a human (or agent on their behalf) asserts a run
  with zero proof: hardware + model + quant + claimed metrics. Stored in a new
  `run_claim` table (schema work), clearly badged `UNVERIFIED`. Never mixed
  into validated leaderboard rankings.
- **B3 — Community plausibility voting**: each claim is votable
  (plausible / impossible) by users; score = vote margin weighted by voter
  credibility. Auto-prior on creation from our own data: roofline prediction
  range + nearest pool measurements ("engine expects 17–23 tok/s here") shown
  next to votes. Disputed claims become challenges: settle them with a verified
  run for bonus reputation (claim → verified conversion loop).
- **B4 — Claim→verification conversion UX**: one-click path from a claim to a
  pre-filled CLI lab session on the claimant's machine ("prove it with one
  command").

## Track C — Human virality

- **C1 — Shareable bestmodel cards**: auto-generated machine ranking cards
  (image/markdown) — "My rig runs Qwen3.6-27B Q5_K_M at 27 tok/s" — sized for
  X/Reddit/Discord; every card links back to the pool page.
- **C2 — Duels/challenges**: "beats/improves X's claim" links; verified runs that
  beat a claim credit both parties and notify the claimant.
- **C3 — Trending claims feed**: weekly "claims deemed impossible" / biggest
  upsets — debate-driven discovery loop for new visitors.
- **C4 — SEO catalog pages**: one page per (hardware × model) with pool data +
  predictions (the modelfit/whichllm-style long-tail, ours is measured).
- **C5 — Embeddable badges**: "verified N tok/s on <gpu>" snippets for forums,
  GitHub READMEs, model cards.
- **C6 — Human-friendly console (Phase 1)**: web console for browse/vote/claim
  without ever touching a terminal; CLI/agent track stays for power users.

## Track D — Diffusion vertical (ComfyUI)

Direction (owner decision, 2026-08-12): extend the platform beyond LLMs to
image-generation models, with ComfyUI as the runtime. Local groundwork lives
in the `cli/comfy-lab/` prompt pack (probe, frozen recipes, workflow
analyzer, instrumentation custom node — S1–S6); platform-side work below.

- **D1 — Image metrics in the report contract**: additive `image_generation`
  block (s/image, s/step, resolution, batch, steps, peak VRAM, recipe_version)
  on contract 0.9.x, mirroring the L01 evolution pattern.
- **D2 — Diffusion model catalog**: seed diffusion models/quants (SDXL, Flux
  schnell/dev FP8/GGUF, Qwen-Image, ...) into the model catalog; schema may
  need a modality discriminator.
- **D3 — Diffusion feasibility predictor**: start empirical (fit from pool
  cells), not physics; the LLM decode roofline does not transfer to UNet/DiT
  step timing. Intake plausibility rules for image runs derive from it.
- **D4 — Distribution**: publish the instrumentation node pack via
  ComfyUI-Manager once contribute (D1) exists — every install is a probe and
  a consumer (same flywheel as L01, larger audience).

## Cross-track notes

- Incentive economy must stay simple at first: reputation points + badges +
  placement. Monetary/token mechanics only after the vote/claim loops show
  organic traction.
- Anti-fraud worker already provides the plausibility priors reused by B3;
  no separate ML needed for launch.
