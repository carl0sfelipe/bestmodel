# Escalation → Fable (2026-09-21): one way to add an intent

> Start here: `docs/POINTERS.md` (job `fable-escalation-2026-09-21`) → this file.
> Handoffs: `docs/handoffs/2026-09-21-music-intent.md`, `docs/handoffs/2026-09-21-3d-gen-intent.md`.
> Binding where it does not conflict: `docs/direction-2026-08-29.md` D1–D2, `docs/direction-2026-09-19.md` D4.

> You are expensive. Do not write code, tests, builds, or deploys. Verify the facts below against the named files, decide, and return a right-sized decision record. The owner has already authorized the executor to implement that record in the same turn. Ambiguity will be implemented literally. Size one story, with paths and acceptance commands, or reject the slice.

> BMAD frame the owner asked for. This is *Clarify → Plan* after two *Build* sessions that stopped on the same limit. §2 is Verify. §3 is Learn. §4 is the decision set. The output is the Plan: a decision record, not an epic, unless you explicitly size an epic and tell the executor to stop after the spec.

---

## 1. Owner request

> "agora escale para o fable para ele decidir e entao voce vai implementar essas melhorias e deixar facil adicionar novos intents e seguir desenvolvendo o bestmodel seguindo os ritos BMAD"

Two handoffs just landed:

- **music** — draft PR #11 (`cursor/music-intent-from-audio-d6bb`, `e33b1ea`, not merged). Intent `music` nested under modality `audio`. Not measured in the pool.
- **image-to-3d** — work lives in a different repo (`rig3d`, HEAD `96b9f62`). Nothing landed in this monorepo. Category id `image-to-3d` was decided there as a **root** category. A staged intake JSON exists there and was **not** submitted. Blessed specs/oracle/validator are ABSENT on that host.

The owner wants the next intent to be easy. v2 D1 already named the disease: the run shape is hand-restated in many places, and prose does not change agent behavior. v3 D4 then allowed a one-off: finish PR #11 by hand because pool-backend sits outside S26. A second intent (3D) hit the same CHECK and stopped. The one-off is now the pattern.

## 2. Verified on this checkout (`main`, 2026-09-21)

Sites that restate "which categories exist", read on `main` (not on PR #11):

| Site | What it says today |
|---|---|
| `apps/pool-backend/src/db.py:18` | `CHECK(category IN ('chat','code'))`. SQLite cannot ALTER a CHECK. `lm_run.tok_s_out REAL NOT NULL`. |
| `apps/pool-backend/CONTRATO-GLOBAL.md:64` | same CHECK literal. The 3D session missed this path (looked at repo root). |
| `apps/pool-backend/src/main.py` `list_models` | 422 unless category is `chat` or `code`. |
| `apps/pool-backend/src/sync_pool.py` `model_category` | code-regex else `chat`. Display name only. |
| `apps/web/scripts/derive.mjs` | same code-regex else `chat`. |
| `apps/web-next/app/home-client.tsx` | handwritten `INTENTS`: chat, code, image, audio, video, vision (`category: null`). |
| `apps/web-next/lib/engine.ts` `metricOf` | image → `imagesPerSec` img/s; audio → `audioXReal` ×real; video → `videoFramesPerSec` f/s; else null (callers use tok/s). |
| Postgres intake | `scenario_kind == "video"` is a special case in public-api / intake-worker. No pool-category CHECK. No `image-to-3d`. |

S26 (contract 0.9.1, modality registry in domain-schema, kill open enums) has **not** started. v2 sizes it large, spec first, after S25. v3 order puts it after the dogfood loop, and puts "PR #11 → music cell" at row 7 as a hand-edit.

PR #11 already hand-built a second copy of the taxonomy (`category.py` + `category.mjs`) and a wider CHECK (`chat|code|image|audio|music|video`). It does not include `image-to-3d`. Its base is `df736bd`; `main` has moved. CI was green there. No music cell was written into derived JSON. `lm_run` was left text-only on purpose.

Id collision: do not use S32–S36 (open PRs on other branches). S29 is unused on `main`. S37 sits above that cluster.

## 3. Learn (what the two sessions actually hit)

1. Adding an intent was rediscovering every allowlist. Music did six of them on a branch and still could not store a run. 3D found two, mis-found the contract path, and stopped.
2. Intent and modality were collapsed. Music is an intent **of** audio. image-to-3d was decided as its **own** root category. A flat CHECK tuple cannot say both without another comment.
3. The metric is part of the intent. tok/s on music or 3D is a lie. The music session forbade `tokSOutMedian` on multimodal cells. The 3D session forbade tok/s and named sec/asset + peak VRAM. `metricOf` is a third handwritten switch.
4. Empty is honest. Both sessions refused invented cells. Music UI empty-state was verified locally. 3D numbers (120–241 s, 20177 MiB, 16 glbs) live only in rig3d and must not be copied in from the handoff.
5. Owner A4s on rig3d (3090 v1/v2, case, RAM/SSD, the uncommitted parametric `mesh_glb`, EXL3 restore) are not this monorepo's decision.

## 4. Decisions

One decision and a short why each. Size each as epic / story / line / explicit rejection. The executor implements only what you mark as this turn's story.

- **D1 — Mechanism.** Thin intent catalog now (one committed document, every allowlist derived from it, a test that fails if a site hardcodes a divergent list) vs merge PR #11 as-is and hand-add `image-to-3d` the same way vs stop and write full S26 first. v2 D1 and the owner's sentence point at the thin catalog. v3 D4 points at the hand-edit. Pick one.
- **D2 — Shape, if D1 is the catalog.** Where the file lives. Which fields a row must have so the next intent is one row: id, UI name, glyph, description, physical modality, whether it is storable as `lm_model.category` (vision: no), primary metric (field, unit, label, rank direction), fields forbidden as the headline, optional classify regex, UI enabled. Consumers you expect in this story: SQLite CHECK builder + rebuild, API filter, derive/sync classifier, web-next `INTENTS`, `metricOf`. Say what stays handwritten.
- **D3 — The two rows.** Confirm or correct: `music` modality `audio`, metric ×real from `audioXReal` or inverted `rtf`, no pool cell. `image-to-3d` root category, metric sec/asset, peak VRAM is not the headline speed, no pool cell, no intake submit. Vision stays listed with no category. Chat/code stay tok/s and stay out of `metricOf`.
- **D4 — PR #11.** Supersede (replay the taxonomy onto the catalog; leave the draft open for the owner) vs merge first vs cherry-pick. Do not tell the executor to merge it unless that is the decision.
- **D5 — Run storage.** Confirm `lm_run.tok_s_out NOT NULL` stays. Music and image-to-3d can be model categories and UI intents with an honest empty state. They cannot be runs in SQLite until a later story grows a multimodal run shape. Postgres `scenario_kind` and domain-schema `MetricKind` stay untouched in this story.
- **D6 — Data honesty.** Explicit rejection list for this turn: no MusicGen numbers in derived JSON, no rig3d submission, no invented `n`, no enabling the static-site pillar just to show an empty category, no EXL3 / RAM / gauntlet edits (other repo).
- **D7 — Story id, paths, acceptance.** Name the spec file. Name the acceptance command the executor must run before calling the story done. Name the one presence check that makes the *next* intent a row rather than a sweep (for example: a fixture intent added only to the catalog appears in the generated CHECK, the API allowlist, and the UI list without editing those files). If that check is not feasible, say so and size the weakest check you will accept.
- **D8 — Order against v3.** v3 row 7 was "PR #11 → music cell". Replace, keep, or split: catalog now, measured cell only when a JSONL exists in-repo.

## 5. Response shape

1. Validation of §2 in at most 8 lines: endorse, correct, or not-verified.
2. Decision record D1–D8 with size and a one-line why. End with an execution order of at most 5 rows.
3. Risks you see that §3 missed (H1+), each one line.
4. The spec skeleton the executor should write before code: objective, non-goals, deliverable paths, acceptance commands. If you reject implementation this turn, the skeleton is the spec only and your last line is `EXECUTOR: STOP AFTER SPEC`.

*Signed: executor, 2026-09-21. Owner authorized implementation of your record in the same turn.*
