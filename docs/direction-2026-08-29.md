# Strategic direction v2 — 2026-08-29 (chronic-cause escalation)

> Decision record for the 2026-08-29 escalation (owner request: meta-analysis
> of the 16-error session log from Story 1.4 + the L03 closure, not individual
> bugfixes). Author: Fable (strategy). Executor: the local agent, after owner
> review. Complements `docs/direction-2026-08-28.md`; where roadmap ordering
> conflicts, this document wins. Error-log evidence lives in the local
> escalation file and in the baton log §7.

## D1 — The chronic cause

**One dominant cause: the shape of a benchmark run is an implicit contract
hand-restated in ~10 places, and nothing mechanical forces the chain closed.**
Domain schema, migration columns, FakeDatabase, the DatabaseSession ABC,
PostgresSession SELECTs and INSERTs, worker hydration SQL, evidence-parser
keys, leaderboard SELECT, CLI report builder, seed catalog: each is a separate
hand-written restatement of "what a run is". When the only client was LLM
inference, LLM assumptions fossilized into every restatement. Adding video was
therefore not "add a modality" — it was "rediscover every place the row shape
is restated", with a green test suite the whole time.

Why the tests stayed green is the second half of the cause: **the test double
is itself one of the hand-written restatements.** Tests assert fake == fake.
FakeDatabase and PostgresSession can drift apart — or agree on being
incomplete — without any red. Cluster A (three occurrences of the same
defect class) is exactly this, and it was *predicted*: finding F8 recorded
"unit tests with fakes don't exercise serialization boundaries" during
Phase 0, and prose alone stopped nothing. That is the meta-lesson of this
escalation: **recorded knowledge without a mechanism at the point of change
does not alter agent behavior.** Every fix below is mechanical, not
documentary.

Verdict on the prior hypotheses:

- **H1 (shotgun change) — confirmed, and it is the core.** The others hang
  off it: H2 is the missing safety net, H3 the missing map, H4 the reason the
  shotgun has ~10 barrels instead of 3.
- **H2 (gate blind to video) — confirmed.** The gate is the only place fake
  and Postgres meet reality; a modality it doesn't exercise is unprotected
  end to end.
- **H3 (tribal knowledge) — confirmed with a refinement:** the knowledge was
  not missing, it was *filed away from the edit site* (AD-1 lived in a ported
  spec; F8 lived in findings). Co-location beats documentation.
- **H4 (schema-enum rigidity) — confirmed as amplifier.** Every new kind
  costs a migration + enum + N sites; the owner's "few required, many opt-in"
  intuition is the right treatment (D2).
- **Missing from H1–H4, named here:** (a) the L03 port was a bulk semantic
  merge between trees with no common ancestor — intrinsically the highest-risk
  operation this codebase has performed; it did not create the weakness, it
  mass-produced instances of it (U4 ported an interface without bodies and
  nothing failed). One-time event, residue is exactly what the D3 harness
  catches. (b) Cluster F was a *strategy-layer* instance of the same disease:
  direction v1 expressed prod deploy as a calendar order ("after the cell
  lands") instead of a dependency ("the cell REQUIRES the L03 schema in
  prod"), and reality inverted it. Rule going forward: specs express
  **preconditions, not schedules**.
- Clusters D and E are a different, smaller family: artifacts derived from
  secondary sources (docs, skeletons) committed without validation against
  the installed reality, plus rented-rig ops drift. Treated by the
  primary-source rule and runbook additions (end of D5), not by architecture.

## D2 — Run schema: few required, many opt-in (endorsed, concretely)

The owner's intuition is endorsed as **contract 0.9.1 direction** (spec id
S26, to be written as an executable spec after S25 lands):

1. **Required core — the honesty invariants, never opt-in:** run identity,
   minimal hardware identity (GPU model/count/VRAM), `model_release_id`,
   `quantization_profile_id`, runtime engine + version, `source_class`,
   signature + digest + nonce chain, `schema_version`, the **one primary
   metric of the modality** (decode tok/s; s/clip), and the peak of the
   bounding resource (`peak_vram_mib` today; F7 adds `peak_ram_mib` as the
   CPU-path equivalent). Making any of these optional makes context-free or
   invented numbers representable — that is the line.
2. **Everything else is opt-in in a single versioned JSONB document**
   (`details`), validated by pydantic at the intake boundary per
   `schema_version`, never constrained by SQL. RAM channels/bandwidth, PCIe,
   storage, wattage, temps, spec-decode config (F4), offload layout: all here.
3. **Promotion rule:** a field moves from JSONB to a real column only when a
   SQL consumer needs to filter or aggregate on it (leaderboard dimensions).
   Promotion = one additive migration + the D3 round-trip row updated in the
   same commit.
4. **Kill DB enums for open vocabularies.** `runtime_engine`, `metric_kind`,
   modality: TEXT + FK to seeded catalog tables — a new runtime or kind
   becomes a seed row, not a migration + enum + code sweep. Postgres enums
   remain only for genuinely closed, load-bearing sets (run/claim status
   machines, `source_class` ladder).
5. **Modality registry in domain-schema** (the direct fix for cluster B):
   one table-driven descriptor per modality — required evidence keys, primary
   metric, duration-consistency check, hydration field list. Worker,
   leaderboard and CLI consume the registry. Adding a modality = one registry
   entry + fixtures, not edits to four scattered functions. AD-1 stands
   (video metrics are run scalars, not `benchmark_metric` rows); the registry
   generalizes it.
6. **Missing opt-in data degrades comparability, not validity:** absence of
   e.g. RAM-channel info attaches an "unknown RAM topology" caveat to offload
   results (see D6 warnings) — incentive to fill without mandating.

## D3 — Fake ↔ real parity: keep the fake, make it prove conformance (S25a)

Killing FakeDatabase is rejected: 300 Python tests in ~5 s is why agents
actually run the suite; gate-as-only-integration-test would slow the feedback
loop that prevents errors. Instead the fake must earn trust mechanically:

1. **Structural inventory check (no DB needed):** a contract test introspects
   the `DatabaseSession` ABC and fails if either backend is missing any
   abstract method implementation; plus an instantiation smoke of
   `PostgresSession` as a registered subclass. This alone would have caught
   "U4 ported the interface, forgot the 7 bodies" at test time.
2. **Behavioral parity suite:** one parametrized set of scenario assertions
   executed against BOTH backends — fake always (in `make test`), Postgres
   against the dev database inside `make gate` / `make test-contract`. Same
   test functions, two fixtures; any divergence is red.
3. **Round-trip field completeness (the drift killer):** for each writable
   entity, write through the session API, read back through the session API,
   and assert field-set equality **generated from the domain model's declared
   fields** — never a hand-maintained list. This catches "INSERT writes 6 of
   9 columns" and "SELECT omits source_class" by construction, including for
   every future promoted column (D2.3).
4. **Rejected:** SQL snapshot tests (brittle, assert formatting rather than
   semantics, high maintenance for agents).

## D4 — Permanent per-folder specs: checklists at the edit site (S25c)

Mechanism (extends the existing AGENTS.md convention, which agent tooling
already auto-surfaces next to edits):

1. Every directory on the run-data path gets an `AGENTS.md` with two
   mandatory sections: **"Change checklist — if you touch X, also touch Y"**
   (the shotgun map made explicit: schema ⇄ fake ⇄ postgres ⇄ worker ⇄
   leaderboard ⇄ seed ⇄ gate) and **"Load-bearing decisions"** (one line per
   decision + pointer, e.g. AD-1, the 95 % feasibility margin, "engine code
   wins"). Initial list: `packages/domain-schema`, `packages/fake-adapters`,
   `packages/roofline-kernel`, `apps/public-api`, `apps/intake-worker`,
   `cli/benchmark-probe`, `infra/migrations`, `infra/seed`.
2. **Site-local `LOAD-BEARING:` comments** (≤ 5 lines) at the exact
   definition sites history shows agents break: `METRIC_UNITS` (AD-1), the
   feasibility margin constant, every `DatabaseSession` ABC method docstring
   gains "lockstep: fake + postgres + contract row, same commit". Cluster C
   happened because the decision was not visible at the point of edit; this
   puts it there.
3. **Maintenance is lockstep, enforcement is presence-only:** whoever lands a
   change updates the checklist in the same commit (same rule as FakeDatabase
   lockstep); the gate greps that each listed directory has an AGENTS.md
   containing the required headings. Content freshness cannot be honestly
   mechanized — presence can.

## D5 — Gate grows a video leg (S25b) + closing rules

Endorsed as specified by the executor estimate (~1 h): `make gate` gains a
mock-ComfyUI POST (no execute; fixture NDJSON) that traverses API → Postgres →
worker validation → leaderboard, asserting (a) the run reaches `validated`,
(b) the leaderboard row **count increases** and the row carries
`source_class` — presence assertions, because the observed failure mode was
"filter silently drops everything", and (c) the run payload round-trips the
video scalars. The D3 parity suite also runs inside the gate. Gate wall-clock
must stay in single-digit minutes or agents will stop running it.

Two non-architectural rules closing clusters D–F:

- **Primary-source rule (cluster D):** any artifact that targets an external
  system (workflow templates, node graphs, API payload skeletons) must be
  validated against the installed reality (dry-run, introspection) before
  being committed as spec/fixture. Goes into the root AGENTS.md rules.
- **Runbook additions (cluster E, ops not architecture):** release binaries
  are built in the oldest-supported-glibc container (ubuntu:22.04), the
  sha256 source of truth for HF downloads is the LFS pointer (never the CAS
  redirect), staging directories are single-writer, and remote rigs never
  generate signing keys — they receive the trusted key or the digest is
  signed locally. Owned by the executor in the kit runbook.
- **Preconditions, not schedules (cluster F):** specs state what a deliverable
  REQUIRES (e.g. "uploading a video cell requires the L03 schema deployed"),
  never a calendar order that reality can invert.

## D6 — Annex A (external insights) consolidated

Already exists — do not rebuild: confidence tiers (= `source_class` ladder +
trust weights), "measured beats reported" (= the honesty ladder, core thesis),
anti-hype tone, external-source ingestion (= harvesters 4.1–4.4, ported in
L03/U5), explained suggestions (= `canirunit suggest` confidence + transfer).

Accepted, in order:

1. **Incomparability warnings** → folded into **S24** (one read-side story:
   source-class badges + tooltips + "differs in quant/ctx/backend/spec-flags"
   warnings instead of silent filtering). The GPT badge/tooltip language is
   S24 copy.
2. **Rich hardware fingerprint** (RAM channels + measured bandwidth, PCIe
   gen/lanes, storage, motherboard) → this is backlog **A4 grown up**; fields
   live as D2 opt-in `details`, collected by the CLI, and power the automatic
   caveats ("result depends on quad-channel"). Folded into **L01 planning**;
   the S26 contract work provides the home first.
3. **Price-per-performance (R$/tok/s)** as a **derived, read-side metric**:
   listing prices are volatile, regional and unverifiable — they live in a
   separate price/listing table (currency- and date-tagged, `reported` class
   at best) joined at read time, and are **never stored on the run row**.
   Product phase: after S24.

Rejected / deferred:

- **AI Deal Hunter + used-listing question generator:** premature before the
  fingerprint (2) and price (3) bases exist; the question generator is cheap
  and can return as a content feature later. **OCR of marketplace listings:
  rejected as scope creep now** (owner's own suspicion, confirmed).
- **Reddit/YouTube/forum scraping as automated sources: rejected on
  principle** — harvesters ingest structured sources only, never forums;
  community numbers enter as human-submitted claims (`reported`), keeping the
  provenance honest.
- GPT's full JSON schema: used as input vocabulary for the S26 opt-in field
  list, not adopted wholesale.

## D7 — modal.com anchor cells (endorsed, with guardrails)

Purpose fits direction v1's D2 exactly: **one measured cell per GPU family we
lack (L4, A10, A100; T4 if trivially cheap) is a transfer-roofline anchor for
the whole family** — the highest-value use of ~US$9 of credit that touches
neither Vast nor prod risk.

Guardrails: run **after S25 lands** (the hardening protects the spend — an
anchor cell uploaded through a pipeline that silently drops fields is wasted
money); LLM standard scenario first (well-trodden path), one cell per family;
spend capped at the existing credit; binaries built per the glibc runbook
rule; signing stays local/owner-key (anchor cells are the owner's own runs, so
this does NOT wait for S23). Stretch goal only if credit remains: one video
cell on A100 as a second diffusion anchor for the f_attn refit (findings
2026-08-29 note). Priority: independent of S23 — platform track and ops track
don't compete; recommended slot is parallel to S23, after S25.

## Roadmap (v2 — supersedes v1 ordering)

| # | Item | What it kills | Effort |
|---|---|---|---|
| 1 | **S25a** contract/parity suite (D3) | cluster A class, permanently | small |
| 2 | **S25b** gate video leg + presence asserts (D5) | cluster B class pre-prod | ~1 h |
| 3 | **S25c** AGENTS.md checklists + LOAD-BEARING comments (D4) | cluster C class, lowers all | half-day |
| 4 | **D7** modal anchor cells (ops, parallel-ok) | coverage gap in transfer | ≤ US$9 |
| 5 | **S23** per-user signing keys (unchanged from v1) | flywheel scale gate | medium |
| 6 | **S24** source-class badges + incomparability warnings (D6.1) | silent filtering; ships the honesty UI | medium |
| 7 | **S26** contract 0.9.1: required-core + JSONB details + catalog tables + modality registry (D2; absorbs F4 spec_decode, F7 peak_ram) | H4 surface for every future kind | large, spec first |
| 8 | **L01** CLI v2 (now also collects the rich fingerprint, D6.2/A4) | — | per its spec |

Items 1–3 are one story cluster (S25, "parity & modality-blind gate") and are
the highest error-reduction per effort in the log: they mechanically prevent
9 of the 16 recorded errors and reduce the recurrence probability of the
rest. The executor writes the S25/S26 executable specs from this document
following `specs/en/` rules; nothing here is implementation.
