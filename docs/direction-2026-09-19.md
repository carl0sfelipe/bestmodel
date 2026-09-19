# Strategic direction v3 — 2026-09-19 (post-incident: beelink → Omarchy, OAuth live)

> Decision record for `docs/ESCALACAO-FABLE-2026-09-19.md`. Author: Fable
> (strategy). Executor: ZCode, after owner review. Complements
> `direction-2026-08-29.md` (v2); where ordering conflicts, this document
> wins. BMAD: this is the Plan output after an unplanned Build+Verify under
> incident. Nothing here is implementation.

## 0 — Validation of the verified state (§3)

Checked read-only on the host at 11:40–11:50 -03, 2026-09-19:

1. **Endorsed:** stack 5/5 up (api recreated 11:25 -03 today, `restarts=0` — the 0c1880f deploy); public 200 on nonce / leaderboard / claims; `www` console base = `https://api.bestmodel.run`; Pages console base = empty (broken as stated); HDD dumps 18/09 17:32 + 19/09 04:10 present; both user timers scheduled; 17 migrations; 551 claims; 2 validated runs; `signing_key` = 0; `oauth_account` = 1; `claim_vote` = **0**.
2. **Corrected:** `app_user` = **3**, not 1: `carl0sfelipe` (08-26, **0 passkeys**), `carl0felipe` (13:36Z today, 0 passkeys — abandoned typo registration), `carl0sfelipe-gh` (OAuth). The moderator handle has **no credential at all** → nobody can act as moderator in prod today (see H5).
3. **New fact:** `~/bestmodelbd.kdbx` (1.6 KB) was created 09:33 -03 today, *after* the new secrets (18/09 17:23). It is the vault for the **new** secrets, not a recovery of the beelink ones — and it sits on the same host as prod.
4. **Not verified by me** (cost/authority): tunnel account state, the Vercel 35-min silence, contents of the off-host backup repo, the scratch restore, the exact reboot count (journal lists 24 boots; consistent with "unstable", not audited).
5. Fresh shells on this host still get `permission denied` on the docker socket (pre-group session). The reboot the HANDOFF predicts is still pending.

## D1 — Prod resilience: light hardening, second origin explicitly deferred

**Decision:** stay on the single Omarchy host. Add three cheap things; reject the rest for now.

- **Story (small) `OPS-1 hardening`:** (a) copy the kdbx off-host (it is encrypted; the passphrase is on paper) — into the private backups repo or removable media, owner's choice; (b) raise the off-host dump cadence to every 6 h (DB is 69 KB; RPO 24 h is a choice, not a cost); (c) one external uptime ping on `/v1/submissions/nonce` (free tier), alerting the owner — the backup-alarm only sees stale dumps, not a dead API.
- **Line:** commit `HANDOFF-OMARCHY` + `docker-compose.omarchy.yml` — that *is* the DR runbook (D7). A monthly manual restore drill; no automated restore test yet.
- **Rejected:** cold standby / second origin. **Precondition, not schedule:** revisit when a validated run arrives from a non-owner signing key, or when a second human moderator exists (same trigger as RAT-3). Until then a second origin protects nobody but the owner.

Why: the SPOF has materialized once, but the blast radius today is one human and 69 KB. Money and attention go to closing the loop (D2/D3), not to duplicating an empty room.

## D2 — Identity: one human, one account — dial today, link flow before S23 wiring

**Decision:**

- **Line (today, owner dial, zero code):** `MODERATOR_HANDLES=carl0sfelipe,carl0sfelipe-gh` in `deploy/.env` → the owner moderates via GitHub login now. Delete the junk user `carl0felipe`. Owner creates the passkey on `carl0sfelipe` in his own browser (still pending since the restore).
- **Story (small) `S31 account linking`:** authenticated link of an OAuth identity to the *current session's* user (begin with a bearer session → callback attaches `oauth_account` to that user instead of auto-creating). Rule for an identity already bound to another user: re-point only if that other user has zero credentials, zero runs, zero votes; otherwise 409. No merge tool. After linking, the owner deletes `-gh`, and the dial goes back to one handle.
- **Reputation:** an OAuth-born account is **L0** like any other. Nothing is inherited from the provider; reputation is earned by signed runs, votes and settled claims. The suffix stays as the collision policy.
- **Order:** S31 lands **before** S23 CLI wiring — signing keys attach to `app_user`; wiring keys while the owner is two users splits attribution on day one.

## D3 — Gate key after the loss: keep the global client key; S23 dissolves the *class*; two orphan runs stay, labelled

**Decision:**

- The global key's role (S23 spec) is *client authenticity*, not user authorship. Keep it, rotated as it is. Confirm the new private half is inside the kdbx (owner check, D1a).
- **The 2 orphan runs stay `validated`.** Validation is a process record from the worker at intake time; the rows still carry their signature and digest. **Rejected:** re-signing with the new key (fabricates provenance); deleting them (they are real 3090 measurements; the wan22 cell is already hidden by the 95 % margin).
- **Line (transparency):** one entry in `docs/transparency.md` (or findings): "runs validated before 2026-09-18 were verified against client key K0 whose public half was lost with the host; K1 since". Honest, cheap, done.
- **Story (medium) `S23b`:** CLI sends `signature_key_id`; gate grows a per-user-key leg; console shows "register key". This is the v1 D2 flywheel gate and it turns future key loss into "revoke, register, old runs stay attributed to the revoked id" — the property we want. Order: after S31.

## D4 — Modal cells (L4 / A10G): route (a), chat+code now, music after PR #11

**Decision:** v2 D7 stands — they are the owner's own measured runs. Publish via contribute, signed with the owner key, `source_class = measured_signed`, `source_url` pointing at the run notes. **Rejected:** (b) derived pipeline — mislabelling down is still mislabelling; (c) holding for S23 — v2 already decoupled anchors from S23.

Preconditions (not a schedule):

1. **Line, urgent:** copy the raw Modal outputs off the agent box into the repo (or the backups repo) *before* anything else — they are one `rm` away from the argos-opt fate (A11).
2. L4 and A10G must exist in `gpu_models` (29 today); if missing, seed from vendor specs first (A10 rules: never guessed).
3. `music` is blocked only on the **pool-backend SQLite** side (`CHECK category IN ('chat','code')`), not on the Postgres intake. **Story (small):** finish PR #11 as-is (add `music` to that CHECK + the site's intent list) — pool-backend is outside the S26 registry scope, so a hand-added value is acceptable there. Then the music cell.

Order: chat+code cells right after D2's dial; music after PR #11.

## D5 — One front: web-next is prod; Pages is a preview, never DR; console becomes single-source

**Decision:**

- `apps/web-next` on Vercel is the only production front (owner-merged in PR #10; this record ratifies it).
- **Line:** GitHub Pages must stop advertising a broken console under the project's name: either set the Pages console base to the API (one line) or stop publishing `/console` there. ZCode picks the cheaper. Pages stays a preview of the legacy static site, nothing more.
- **Rejected:** Pages as a fallback for the prod front. One unexplained 35-min Vercel delay is not evidence, and web-next is a Next.js app — a static mirror is not a like-for-like fallback without work nobody has asked for.
- **Story (small) `WEB-1 console single-source`:** the console (and the derived data snapshot) live in exactly one place and are *copied at build time* into web-next — never two hand-maintained copies. This is the v2 D1 disease (hand restatement) on the front; fix it mechanically the same way. Update `docs/en/deploy.md` in the same story (it still sells Pages as the DNS cutover).

## D6 — Activation: nothing outward until the owner can run the whole loop; then S24

**Decision:** no campaign, no challenge, no announcement until the **dogfood loop** is green — one human (the owner, as one account) can: log in with passkey and GitHub → vote on an imported claim → settle a claim with a signed run attributed to his user → see it rendered with its source-class badge. Today steps 1, 3 and 4 are not possible (0 credentials on the moderator, keys unwired, S24 unbuilt). Pushing strangers into that is how you get zero-vote products with 551 claims.

- **Next growth item once the loop closes:** **S24** (source-class badges + incomparability warnings) — v2 order stands; the claims tier already shipped in web-next (PR #10), so S24 is the read-side half that makes it honest.
- **Rejected:** a "measurement challenge" funded by the Modal credit — the credit buys transfer anchors (v2 D7), not marketing. **Deferred:** claims-tier-in-feed — a slice already exists; nothing more until there is a second voter.

## D7 — Session debt: commit now; it precedes everything

**Decision:** this is minutes, and it is the DR runbook. Do it first.

- Commit: `deploy/docker-compose.omarchy.yml`, `docs/HANDOFF-OMARCHY-2026-09-18.md`, `docs/POINTERS.md`, `docs/FABLE-BRIEF-2026-09-19.md`, the escalation, this file.
- systemd units in git: use the `%h` specifier (`%h/Work/bestmodel/...`) so the same unit works for `beelink` and `carlos`; the ssh hop stays **out** of the repo (host quirk, documented in the HANDOFF).
- Register the OAuth story under a non-colliding id in `specs/en/AGENTS.md` (`S30-oauth`, noting the backlog's `S30` mural). Commits are not renamed.
- Pages console: D5 line. Junk user: D2 line.

## Order of execution

| # | Item | Size | Why here |
|---|---|---|---|
| 0 | D7 commits · D1a kdbx off-host · D4.1 Modal raw outputs backed up | lines | things that can still be lost today |
| 1 | D2 dial (`MODERATOR_HANDLES`, delete `carl0felipe`, owner passkey) | lines | moderation is off in prod |
| 2 | OPS-1 hardening (ping, 6 h cadence) | story S | cheapest insurance |
| 3 | D5 Pages console line | line | stop advertising a broken console |
| 4 | D4a L4/A10G chat+code cells | ops | anchors, independent of platform work |
| 5 | S31 account linking | story S | before keys touch users |
| 6 | S23b CLI wiring + gate leg | story M | flywheel gate; dissolves the key-loss class |
| 7 | PR #11 → music cell | story S + ops | |
| 8 | S24 badges + warnings | story M | first outward-facing item, after the loop closes |
| — | second origin, campaigns, challenges | rejected / precondition-gated | see D1, D6 |

Then S26 / L01 per v2.

## H5+ — risks not in the escalation

- **H5 (verified):** the moderator handle has zero credentials → moderation is effectively disabled in prod; reports stay open. Fixed by D2's dial.
- **H6 (must verify, one grep — ZCode):** `register/options` now answers 200 for an *existing* handle. If `register/verify` does not require a live session of that user (or reject existing handles), that is account takeover by passkey enrolment. Confirm before the owner enrols.
- **H7:** the Modal measurements exist only on an agent-box clone — same loss class as argos-opt and the beelink. D4.1.
- **H8:** the kdbx lives on the prod host; host death = vault death again. D1a.
- **H9:** until the reboot, every fresh shell on this host fails docker calls with `permission denied`. An agent could read that as "stack down" and "repair" it. The HANDOFF documents it; the reboot closes it.
- **H10:** two fronts × two consoles × two data snapshots is the v2 D1 disease (hand restatement) reborn on the front. D5 story.
- **H11:** GitHub is now code, off-host backups, Pages, an OAuth provider and the alarm — one vendor. Acceptable at this stage; recorded, no action.
- **H12:** there is no record of which commit is live in the API container (manual `up -d --build`, recreated today). **Line:** surface the git sha in the image (build arg → `/v1/health`) so "what is in prod" is verifiable, not remembered.

## Pointers (owner's extra request — sized: one line + one presence check)

**Adopt `docs/POINTERS.md` v0 as a standing convention.** The mechanism already exists: the root `AGENTS.md` is auto-injected into every agent session and now points at the catalog instead of prescribing a seven-file ingest — that *is* a mechanism at the point of read, so no new gate for reading. One addition, inside the existing S25c presence grep: `docs/POINTERS.md` exists and every `docs/**/*.md` appears in it under some verb (catch-all rows allowed). STALE rows are lockstep with the change that made the file wrong (same rule as FakeDatabase). Jobs and folders stay two catalogs — different axes (read vs edit). `llms.txt` keeps only the `cold-start` job; external agents get no strategy pointers. Rejected: per-folder OPEN/SKIP cards (would duplicate the map).
