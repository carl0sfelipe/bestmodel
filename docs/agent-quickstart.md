# Agent quickstart — cold checkout to ranked, tested numbers

You are an AI agent on a Linux box (cloud VM, workstation, container).
This page is the shortest honest path from `git clone` to (1) knowing the
hardware you run on, (2) the best models measured for it, and (3) running
the probe yourself. Every command here was executed on a clean checkout
on 2026-09-18 — none of them needs the bestmodel API, a key, or a token.

Self-check in one command after cloning: `make agent-smoke` (builds both
CLIs and runs this whole page's flow with tiny budgets).

House honesty ladder (applies to everything you emit): **measured** =
n≥3, **reported** = 1–2, community pool data = **harvested**, stub/mock
output = **SIMULATION**. Never present one as the other; never round a
number in the flattering direction; hardware you cannot detect stays
undetected — never guessed.

## Download a release (or build from source)

Prebuilt binaries for Linux x86_64 and macOS arm64 are attached to every
version tag on the GitHub Releases page — checksummed (`SHA256SUMS-*`),
built by CI in the same run that publishes them:

```bash
# from https://github.com/carl0sfelipe/bestmodel/releases (pick the tag)
curl -LO https://github.com/carl0sfelipe/bestmodel/releases/download/v0.1.0/benchmark-probe-x86_64-unknown-linux-gnu.tar.gz
tar -xzf benchmark-probe-x86_64-unknown-linux-gnu.tar.gz
chmod +x benchmark-probe canirunit && export PATH="$PWD:$PATH"
```

Verify against the SHA256SUMS file from the same release before trusting
the binary. There is no one-line installer yet.

## 0. Build (once)

```bash
git clone https://github.com/carl0sfelipe/bestmodel.git
cd bestmodel
cargo build --release -p canirunit -p benchmark-probe
export PATH="$PWD/target/release:$PATH"
```

No Rust? `curl https://sh.rustup.rs | sh -s -- -y --profile minimal`
(then source `~/.cargo/env`). The build needs a C toolchain plus make,
perl and pkg-config (Debian/Ubuntu: `apt install -y build-essential
pkg-config perl`; the OpenSSL used by the probe is vendored and builds
from source). The optimizer dep is vendored in-repo
(`third_party/argos-opt`): any checkout builds.

## 1. Detect the hardware you are running on

```bash
benchmark-probe --runtime mock --model qwen3:8b
```

The first lines are the real topology (Linux: `nvidia-smi` +
`/proc/cpuinfo` + `/etc/os-release`; macOS: `system_profiler` +
`sysctl`):

```
GPU: NVIDIA GeForce RTX 3090 (24 GiB)
CPU: Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz
OS: linux Omarchy
```

Everything under `Running mock benchmark` is MOCK — ignore those
metrics; you ran this for the topology. On Linux without an NVIDIA
driver the GPU list is empty (not detected ≠ no GPU).

## 2. Estimate the best models for this hardware

Map the detected GPU to the pool's rig id: lowercase
`maker-family-vram` (`rtx-3090-24gb`, `a100-40gb`, `m4-pro-24gb`), with
`-x2`/`-x4` for multi-GPU. Don't guess — ask the corpus, filtering by
whatever the topology told you:

```bash
canirunit rigs --runs apps/web/data/derived/pool.json --filter rtx-3090
```

No discrete GPU? The pool carries CPU rigs too (`cpu-amd-ryzen-*`,
`cpu-intel-*`) and Apple machines (`m4-pro-24gb`, `m1-max-64gb`).
And if your `--gpu` value misses, `suggest` itself prints the closest
ids the corpus actually knows (deterministic ranking, never invented).

Rank (offline, deterministic, no LLM anywhere in the path):

```bash
canirunit suggest --gpu rtx-3090-24gb --task decode_tok_s \
    --runs apps/web/data/derived/pool.json \
    --gpus cli/canirunit/gpu_transfer_specs.json
```

- Pool entries load as `source_class=harvested` (community medians —
  the note on stderr says so, and confidence reflects it: a single
  harvested run scores 0.228, not 0.9).
- GPU absent from the pool? With `--gpus`, the roofline transfer kicks
  in (`match_class: same_arch_family` / `roofline_transfer` — always
  labeled derived, never "measured on this machine").
- Exit code 3 = no data at all for that GPU: the honest answer is "be
  the first to publish a signed run", not a guess.

## 2b. Plan: what SOTA should run here (catalog + predictors)

```bash
benchmark-probe plan --gpu rtx-3090-24gb
benchmark-probe plan --gpu rtx-3090-24gb --json
```

Ranks catalog models for the rig through the honesty ladder: `measured`
(pool median on this rig, n>=3) > `reported` > `extrapolated`
(bandwidth-scaled from a measured cell) > `formula` (roofline). Every row
declares its basis; a GPU outside the snapshot exits 3 with the closest
known rig ids — never a guess.

## 3. Tune the serving flags (TPE lab — SIM by design)

```bash
benchmark-probe lab --stub --trials 60
```

Searches the llama.cpp serving space (ngl/ctx/threads/kv-cache/
flash-attn) with TPE against a deterministic SIMULATION of a 24 GiB
class rig. Output is SIM-marked and **is not a benchmark claim**; it
exercises the full loop (failures → null trials, immutable lab dirs in
`experiments/<label>/` with `meta.json`, `index.jsonl`, `best.json`).

## 4. Test for real (only if a runtime is installed)

The probe scans PATH for llama.cpp and ollama. Dry-run first — it just
prints the exact command it would run:

```bash
benchmark-probe --runtime ollama --model qwen3:8b --print-command
```

Then, with the model pulled (`ollama pull qwen3:8b`):

```bash
benchmark-probe --runtime ollama --model qwen3:8b
```

`--runtime mock` always works (what CI uses). Real numbers only come
from a real runtime.

## 5. Publishing (owner-only — skip)

`--sign`/`--upload` need an Ed25519 key and an API token that only the
owner issues. As an agent, do not attempt it; a mock run is never
signed. Local reports are fine: add `--output report.json`.

## Hard "do not"

- Do not swap `third_party/argos-opt` for any crates.io crate (see
  `incidents/2026-09-18-agente-substituiu-dep-load-bearing` in the
  llms.surf orchestrator; the crates.io `optimizer` is a different
  optimizer).
- Do not weaken a test to make a build pass — fix the code or report.
- Do not edit measured numbers, spec-pinned bars, or lab history.
