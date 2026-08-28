# Strategic direction — 2026-08-28

> Decision record produced under the multi-agent baton contract
> (`docs/HANDOFF-2026-08-28.md` §6, local). Author: Fable (strategic
> direction), execution owner: the local agent. Four decisions, D1–D4,
> answering the four open strategic questions in order. Rationale lives here;
> the executable plan for D1 lives in `specs/en/L03-engine-unification.md`.

## D1 — Lineage unification: curated port into this repo; engine repo frozen after

**Decision:** this monorepo (`carl0sfelipe/bestmodel`) is canonical. The
engine lineage (epics 1–5 in the private `CanIRunIt` clone) is ported here as
fresh curated commits — spec `L03`, stories U0–U6 — and the engine repo is
then tagged and frozen as a read-only archive.

**Why this direction (and not the reverse):** the public repo is the one that
is deployed, pushed, licensed (AGPL/MIT split), carries ten applied
migrations and live production data (551 imported claims, 1 published cell),
and was deliberately born with a clean single-commit history that keeps
private artifacts out. Reversing the flow would re-contaminate that boundary.

**Why a curated port (not cherry-pick, not subtree):**

- The two histories are unrelated by construction (public squash birth), so
  cherry-picks have no common ancestor and engine commits touch private paths.
- Hard evidence that blind tree merging cannot work: migration id collision —
  engine `0005_recipe_and_video` / `0006_contributor_reported` vs public
  `0005`–`0010` social tables already applied in production. Engine
  migrations are renumbered `0011`/`0012` in the port.
- The divergence is bilateral but small and enumerable: on the shared
  `benchmark-probe` the public side added settle-claim + portability fixes
  while the engine side added the ComfyUI adapter; on the API only five
  shared files differ, everything else is one-sided additions.

**Sequencing note:** U0 (committing the loose rig-session fixes in the public
tree, plus the missing test update that kept `cargo test` from compiling) was
executed on 2026-08-28 as part of this decision — the first conflict named in
the handoff is resolved. The port does not touch production and does not
block the in-flight Story 1.4 collection; applying migrations 0011+ to prod
is an owner-gated deploy scheduled after that cell lands.

**Bonus:** the port delivers most of backlog Track D (D1 image metrics in the
contract, D2 diffusion catalog seeds, D3 empirical diffusion predictor
groundwork) — it is the roadmap we already had, not new scope.

## D2 — Bootstrapping measured cells: prove the pipe, then multiply signers, then farm the claim pool

The flywheel (claims → votes → settle) currently has 551 UNVERIFIED imported
claims and one measured cell. Order of operations:

1. **Land the two in-flight cells.** Story 1.4 (Wan 2.2 FLF2V q-fp8 measured
   cell) and the Flash Next cell (rerun with the single-turn flag fix). These
   prove the contribute pipeline end-to-end and give the leaderboard its
   first diffusion cell sitting honestly next to its `derived` sibling —
   measured outranking derived is the product thesis made visible.
2. **Per-user signing keys before any community push.** Today the intake
   trusts a single signer, so only the owner can settle anything. That makes
   community settle campaigns pointless until fixed. This is the next
   platform story after L03 (see D3) and the real scale gate of the flywheel.
3. **Farm the imported pool deliberately.** Rank the 551 claims by vote
   engagement × catalog coverage gap; the owner settles the top claims
   reachable with hardware in hand (3090-class first), publishing share cards
   for each settled claim. Then push the one-click "prove it" path (backlog
   B4 — pre-filled CLI command from the claim page) at external claimants.
4. **Optimize for transfer anchors, not cell count.** A measured cell on a
   new GPU family calibrates roofline transfer for the whole family;
   duplicate cells on the same family add little. Coverage of distinct
   families is the metric that matters for `suggest` quality.

Imported claims never enter the leaderboard (standing decision); their
conversion rate into `settled_verified` is the growth metric of the platform.

## D3 — Public roadmap after S22 (order and why)

1. **L03 — engine unification** (spec committed today). Foundation for
   everything below; also closes most of Track D.
2. **S23 — per-user signing keys** (was debt item #2 in the 25/08 handoff):
   register an Ed25519 public key per account, intake validates each run
   against its submitter's key instead of the single trusted key. Spec to be
   written when L03 lands; it precedes any community campaign (see D2).
3. **S24 — source-class visual badges** in the web surface (site, console,
   cards). The data is already public through the API after L03/U4; this was
   the engine lineage's single leftover software item.
4. **L01 — CLI v2 Local Lab**, only after unification: `plan`/`lab`/
   `report`/`contribute` must be built on the merged probe + suggest so the
   work is done once. Resolve backlog questions A1–A6 during its spec phase.
5. **C2 duels / C3 trending feeds** after S23, as the community pull layer on
   top of a settle flow that anyone can sign.

Independent physical/execution items (no ordering constraint against the
list above, owned by the local agent): Story 1.4 collection and upload; Flash
Next cell rerun; the dual-node cost-benefit table for the pending hardware
estimate; the `kv_layers` hybrid-model fix in the roofline kernel (currently
produces false-negative VRAM verdicts for models with KV on a subset of
layers — an honesty bug on the safe side, but still a wrong verdict; belongs
in `docs/findings.md` when fixed).

## D4 — Open-core boundary and the cloud: hold, with explicit unlock criteria

**Decision: do not build `bestmodel-cloud` yet.** The skeleton stays a
skeleton until all three unlock criteria hold:

1. L03 done (one canonical engine to build on);
2. Reseller terms-of-service for the target GPU providers validated and
   written down (flagged in the 25/08 handoff — margin built on top of
   unvalidated resale terms is a business bug);
3. First organic flywheel signal: at least ~10 `settled_verified` cells from
   at least 3 distinct users (i.e., after S23), proving the open platform
   generates the data the paid product would monetize.

**Boundary (reaffirmed, already in L02):** the cloud side integrates through
public HTTP APIs only — no shared code, no shared database; removing it must
leave every open feature functional. MIT packages may be consumed by the
cloud side as libraries; that is what MIT is for. AGPL `apps/**` protect the
hosted platform itself.

**Product direction when unlocked:** the recipe is the commercial unit. A
recipe is already a first-class, deterministically-hashed entity; `suggest`
already explains its confidence. The minimum viable hosted product is
"run this recipe on managed hardware" — one click from a suggest result to a
hosted endpoint, priced on convenience, never on locking up the open data.

---

*Committed together with `specs/en/L03-engine-unification.md`; registered in
the baton log (§7) of the local handoff. No operational secrets in this file
by design.*

## Release note — L03 complete (2026-08-28, ZCode)

U0–U6 executed per `specs/en/L03-engine-unification.md`: U1 domain schema +
diffusion-step kernel (8c55c86), U2 migrations 0011/0012 + seed union (8772c77),
U3 ComfyUI adapter bilateral merge (17a5c40), U4 reported/transparency API
surface (9a3b0c3), U5 canirunit CLI + harvester (b22dc72), U6 this docs/archive
freeze. Suites at close: 300 py + 58 rs, zero failures. The engine lineage is
frozen as a read-only archive (tag `engine-epics-1-5-final`); all new work
happens here. Migrations 0011+ remain owner-gated for prod deploy (after the
Story 1.4 cell lands).
