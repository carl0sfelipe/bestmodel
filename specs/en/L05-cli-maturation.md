# L05 — CLI maturation ("what's missing to be a normal CLI") + scale

> Escalation source: owner, 2026-09-21 v2 ("what's missing to be a normal CLI?"
> then "scale"). This epic is the Clarify → Plan output: a decision record plus
> a right-sized story cluster (S37–S42) that walks the current binary — a
> single-run measurement probe with one experimental subcommand — up to a CLI a
> user installs, invokes, and runs through the full loop, with **nothing
> promised before it exists** (the phantom `canirun.it/sh` lesson still fresh).

This file is the epic umbrella: it carries the numbered decision record
(including explicit rulings on backlog A1–A6) and the map/order of the stories.
Each story is a self-contained spec in `specs/en/` with a mechanical
`## Oráculo`.

## Validation (spot-checked on the built `target/release/`, 2026-09-21)

- `--version` is absent: `benchmark-probe --version` → "unknown argument", exit
  2; the semver only appears inside the usage banner (`VERSION` const exists in
  `cli/benchmark-probe/src/main.rs`).
- `-h`/`--help` work (exit 0, rich usage); `lab` has its own mini-help.
- Two unrelated binary names ship one product: `benchmark-probe` (measures) and
  `canirunit` (queries the pool). Both present under `target/release/`.
- Parsing is manual in both crates — no `clap`/`structopt` in either
  `Cargo.toml`; error style diverges between the legacy parser and `lab`.
- Only `lab` of L01's `plan`/`lab`/`report`/`contribute` exists (L03A stub,
  SIM-marked). `argos-opt` is vendored at `third_party/argos-opt` (owner-
  authorized reconstruction, no remote) → blocks `cargo publish` (backlog A11).
- S23 backend (signing keys) exists: migration `0013` + `POST/GET/DELETE
  /v1/auth/signing-keys`; the `signing_key` table is empty and the CLI never
  registers a key (HANDOFF §8 item 2).

## Rulings on the open backlog decisions (A1–A6, plus A9/A11)

- **A1 — optimizer: CLOSED.** Owner decided (2026-08-30): the optimizer is our
  own crate `argos-opt` (Rust, argmin-inspired, agentic), consumed by path
  until published. Not reopened here. Residual = A11 (publish it).
- **A2 — model acquisition: CLOSED.** Owner decided: both paths (Ollama
  auto-pull, llama.cpp manual GGUF). It is a sub-scope of the real-measurement
  `lab`, which is owner-blocked (Vast suspended) and therefore **out of this
  cut** — the stub `lab` is enough skeleton for `report`/`contribute`.
- **A3 — contribute consent: CLOSED.** Owner decided: opt-out **transparent**
  (visible, pre-checked first-run box; unchecking always honored) with the
  llms.surf giveaway gamification. Drives S41's consent UX.
- **A4 — Linux topology: DONE** (NVIDIA + common-Linux path, 2026-09-18).
  Non-NVIDIA Linux GPUs stay undetected by design (never invented).
- **A5 — roofline threshold (0.92 vs measured 0.94): KEEP OPEN.** It is a
  calibration/findings decision, not a CLI one. It does **not** block S37–S42;
  it only gates whether *contributed lab runs pass validation* (they currently
  quarantine). S41 acceptance is "upload accepted (202) and stored", never
  "validated" — validation acceptance waits on A5. Recommend a separate
  owner/data ruling on the corpus, unchanged by this epic.
- **A6 — MoE residency model: KEEP OPEN.** Predictor calibration, not CLI. Does
  not block; it only affects `plan`'s prediction accuracy for MoE models, which
  S39 surfaces honestly via the basis label (never presents an under-predicted
  number as measured).
- **A9 — `plan` must query catalog SOTA, not only local measurements:**
  becomes **S39** (`plan`).
- **A11 — publish `argos-opt` as a git/registry dep: KEEP OPEN, owner-gated**
  (recover the original tree from Time Machine, then publish). It blocks
  crates.io only; S38 routes distribution around it (a release binary is built
  from the workspace with the vendored dep — no publish needed).

## Decision record

Size legend: **story** (one dispatchable spec) · **line** (backlog one-liner,
no spec) · **rejection** (explicitly not done, with reason).

### D1 — Adopt `clap` as the ergonomics baseline — **story → S37**
Decision: migrate both binaries to `clap` (derive), preserving every existing
flag and the `lab` behavior, and get `--version`/`-V`, uniform `--help`,
consistent error style and (optional) shell completion in the same move.
Why: the agent flags and the three new subcommands multiply the manual
parser's surface across two crates whose error style already diverges;
hand-wiring `--version` now just to rip it out for clap is waste. Dep weight is
marginal — the probe already links reqwest/openssl/ed25519.
Unblocks: a real subcommand tree for S39/S40/S41/S42 instead of more
special-casing before the legacy parser. Kills: the divergent manual parsers
and the missing `--version`.

### D2 — Do **not** merge the two binaries now — **rejection (YAGNI)**
Decision: keep `benchmark-probe` and `canirunit` as separate binaries; add only
cross-discoverability (each `--help` gains a "SEE ALSO" pointing at the other),
folded into S37.
Why: a hard merge is a churny refactor with a real compat cost (`/cli` docs,
`make agent-smoke`, and every runbook invoke both names); the two have distinct
jobs (measure vs. offline pool query). Revisit only if a shared subcommand
dispatcher makes it cheap.
Kills: a speculative rename/merge that buys nothing a "SEE ALSO" line does not.

### D3 — Ship GitHub Release binaries as the real install path — **story → S38**
Decision: a tagged-release CI workflow cross-compiles both binaries, publishes
checksummed artifacts to GitHub Releases, and `/cli` offers "download a
release **or** build from source". Only binaries CI actually built are
published — no fake installer.
Why: "install, invoke, use" needs a prebuilt artifact that exists today;
crates.io is blocked by A11 and a one-line installer (D6) had no artifact to
host — a Release binary is that artifact.
Unblocks: D6 (a download-based installer becomes honest once a real binary
exists). Kills: the "only install path is `git clone` + `cargo build`" ceiling
without inventing anything.

### D4 — crates.io publish stays blocked on A11 — **line**
Decision: `cargo publish` is a backlog line, to be done **after** A11 recovers
and publishes `argos-opt` as a git/registry dep. Not in this cut.
Why: a path dep cannot be published; forcing it would either vendor a private
tree into crates.io or break the build. S38 makes this non-urgent.

### D5 — `plan` command — **story → S39** (realizes A9)
Decision: implement `benchmark-probe plan` — ranked candidates from **catalog
SOTA + predictors**, offline-capable (predictors-only fallback), `--json`. It
is exactly what `/cli` quarantines today.
Why: A9 verified that `canirunit suggest` ranks the lab corpus but never
proposes catalog SOTA; `plan` is the missing command and the loop's entry.
Kills: the "no first real step after `lab`" gap; lets `/cli` un-quarantine
`plan`.

### D6 — `report` command — **story → S40**
Decision: implement `benchmark-probe report` over an existing
`experiments/<label>/` lab dir → table `config | measured | predicted | delta`
+ best command line; `--json`/`--markdown`.
Why: `lab` already writes `index.jsonl`/`best.json`; `report` reads them — it
needs no engine run and no A5 (it displays the delta, it does not gate on it).
Kills: the "lab produces data nobody can read" gap.

### D7 — `contribute` command (existing contract 0.9.0) — **story → S41**
Decision: implement `benchmark-probe contribute` — batch-convert the best
validated lab cell(s) into **existing** contract-0.9.0 signed reports and
upload via the **existing** intake, with A3's opt-out transparent consent and
`--no-upload`. Per-user attribution comes from S42.
Why: contribute closes the flywheel; using the current contract keeps it
CLI-only (no backend). The 0.9.1 evolution (statistics/tuning/spec_decode
blocks + worker anti-fraud) is a **separate deferred backend line**, not this
cut.
Kills: the "measured locally, never shared" dead end. Note: acceptance is
"upload accepted/stored", not "validated" — validation waits on A5.

### D8 — `login` + per-user signing-key registration — **story → S42** (S23-CLI)
Decision: implement `benchmark-probe login` — store an account token (web-issued
via existing `POST /v1/auth/tokens`) in a config file and register the local
Ed25519 **public** key via the **existing** `POST /v1/auth/signing-keys`; later
`--upload` attaches `signature_key_id` (opt-in path already in submit).
Why: today `--upload`/`--settle-claim` need a hand-pasted token and every
submission verifies against one global key; S23's backend exists but the CLI
never registers a key (HANDOFF §8 item 2). No new backend.
Unblocks: per-user contribution attribution (feeds S41 and the llms.surf tier
signal). Kills: the friction of manual token env + the empty `signing_key`
table. Interaction with the gate: submissions gain `signature_key_id`; the
legacy global-key path stays valid (D2 opt-in from S23) — the 2 legacy
`validated` runs are an ops/backfill matter, not this story.

### D9 — Universal `--dry-run` is rejected — **rejection (YAGNI)**
Decision: no universal `--dry-run`; keep per-command dry behavior where it
already means something (`--print-command`, `--no-upload`).
Why: a blanket flag adds surface with no distinct behavior on read-only
commands.

### D10 — Honesty ladder & phantom guard on every doc/spec touch — **contract**
Decision: no command, flag, or subcommand is documented or invoked in the same
commit that does not dispatch in `cli/benchmark-probe/src/main.rs`; `/cli`
(L04 S33) un-quarantines a subcommand only in the commit that ships it.
Why: the `canirun.it/sh` phantom is the standing lesson.
Kills: promising surface before it exists.

## Story map

| Story | Title | Size | Depends on |
|---|---|---|---|
| S37 | `clap` ergonomics baseline (`--version`, uniform help/errors, exit codes, SEE ALSO, optional completion) | story | — |
| S38 | GitHub Release binary distribution (tagged CI, checksums, `/cli` download option) | story | — |
| S39 | `plan` command (catalog SOTA + predictors, `--json`) | story | S37 |
| S40 | `report` command (measured-vs-predicted table, `--json`/`--markdown`) | story | S37 |
| S41 | `contribute` command (contract 0.9.0, A3 consent, `--no-upload`) | story | S37, S42 |
| S42 | `login` + per-user signing-key registration (existing endpoints) | story | S37 |

## Implementation order (for ZCode dispatch)

1. **S37 first** — the clap baseline is the keystone; S39/S40/S41/S42 add
   subcommands on top of it.
2. **S38 in parallel with S37** — the release workflow cross-compiles the
   binaries as they are; it does not depend on the parser refactor.
3. **After S37, in parallel**: S39 (`plan`), S40 (`report`), S42 (`login`).
4. **S41 (`contribute`) after S42** — it attaches per-user attribution
   registered by `login`; it also pairs naturally with `report`'s reader.
Parallel lanes: `{S38}` ∥ `{S37 → {S39, S40, S42} → S41}`.

## Rules (apply to every story in this cluster)

- Honesty ladder is non-negotiable: never document, print, or dispatch a
  subcommand/flag the binary does not ship in the same commit; never invent a
  number, a metric, a deadline, or a source.
- Anti-phantom: never fake a missing capability behind a stub that reports
  success; a not-yet command exits non-zero with a clear "not implemented",
  never a fabricated result. (Rust analogue of "never use `declare const` as a
  workaround" — do not stub a table/endpoint/flag into existence.)
- Web surface (L04) is out of this epic; the only coupling is that `/cli`
  (S33) un-quarantines a subcommand when that subcommand lands here.
- Backend: S41 and S42 use **existing** endpoints only; a diff that adds an
  API/worker/migration is out of contract (contract 0.9.1 is a separate
  deferred line).
- Every acceptance criterion is mechanically verifiable (a command + expected
  exit); each spec carries a `## Oráculo` with a raw `- comando:` line.

## Hygiene note (line)

L01's internal wave labels (`L01`…`L07`) collide with epic **file** ids
(`L03`, `L04`, now `L05`). Recommend relabeling L01's internal waves to
`W1`…`W7` in a docs-only pass so "L04/L05" unambiguously mean the epic files.
