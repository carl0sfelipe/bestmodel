# Strategic direction — 2026-09-21 (intent catalog)

BMAD: this is the **Plan** (Clarify → Plan after two Build sessions that stopped on the same CHECK). Nothing here is implementation. Author: Fable. Executor implements the story in §Spec skeleton, nothing else.

## 0 — Validation

1. Endorsed: `apps/pool-backend/src/db.py:18` `CHECK(category IN ('chat','code'))`, `lm_run.tok_s_out REAL NOT NULL` (line 29); `CONTRATO-GLOBAL.md:64` same literal; `main.py:124` 422 outside `("chat","code")`; `sync_pool.py:193` code-regex else `chat`, display name only; `derive.mjs:143` same regex; `home-client.tsx:22-29` six handwritten rows, vision `category: null`; `engine.ts:31-36` `metricOf` three-way switch, null for text.
2. Corrected — §2 undercounts: `home-client.tsx:108` `multimodal = category === "image" || "audio" || "video"` is a seventh restatement, and `engine.ts:10` `Cell.category?: "image" | "audio" | "video"` is an eighth. Both are consumers in this story.
3. Corrected — §2 "S26 has not started" is right, but §2 frames pool-backend as *inside* the eventual S26 fix. It is not: pool-backend must not import `packages/`, so S26's domain-schema registry can never reach `db.py`. The catalog has to be a file, not a Python module.
4. Not verified (out of the permitted set): Postgres `scenario_kind == "video"` special case; PR #11 contents (`category.py`/`category.mjs`, base `df736bd`) — taken from the handoff only.
5. Not verified: whether `apps/web/scripts/check.mjs` and `apps/web-next/tests/` exist on `main`. Spec below does not depend on either.

## D1 — Mechanism

**Decision:** Thin intent catalog now: one committed JSON, one small loader per language (Python / Node / TS), every allowlist in §0 derived from it, and a presence test that adds a fixture row to a temporary catalog and asserts it reaches the SQLite CHECK, the API filter and the classifier without touching those files. Rejected: merge PR #11 and hand-add `image-to-3d` (PR #11's `category.py` + `category.mjs` pair is the twin disease with a nicer coat; a third intent would be a third sweep). Rejected: write S26 first (S26 is Postgres/domain-schema; the two sites that actually stopped both sessions live in pool-backend and web, outside S26's reach; the catalog becomes S26's seed).
**Size:** story M (one executor turn; ~15 files, mechanical).
**Why:** v2 D1 — knowledge without a mechanism at the edit site changes nothing; two sessions proved it again on the same line of `db.py`.

## D2 — Shape

**Decision:** `packages/intent-catalog/catalog.json`, read by path (env override `BESTMODEL_INTENT_CATALOG`), never imported as a package by pool-backend. Top level: `version` (int), `fallbackIntent` (`"chat"`), `modalities` (closed list: `text, image, audio, video, 3d`), `intents` (ordered array; file order is both UI order and classifier precedence). Each row, all fields mandatory:

| field | type | meaning |
|---|---|---|
| `id` | kebab string, unique | `lm_model.category` value and UI intent id |
| `name` | string | chip label |
| `glyph` | string | chip glyph |
| `desc` | string | chip description |
| `modality` | one of `modalities` | physical domain of the measured output |
| `storable` | bool | may be `lm_model.category` and a valid `?category=` (vision: false → chip disabled, `category: null`) |
| `metric` | `{field, unit, label, higherIsBetter}` | the one headline speed for cells of this id |
| `forbiddenFields` | string[] | fields a derived cell of this id must not carry (`tokSOutMedian` on every non-text row) |
| `classify` | regex string or null | applied case-insensitively to `display_name + " " + hf_id`; first match in file order wins; null = never auto-assigned |

Consumers this story (derive, do not restate): `db.py` CHECK + rebuild, `main.py` filter, `sync_pool.py` classifier, `derive.mjs` classifier, `home-client.tsx` `INTENTS` and `multimodal`, `engine.ts` `Cell.category` type and `metricOf`, `CONTRATO-GLOBAL.md` CHECK line (bound by test). Stays handwritten, recorded as debt in the spec: `apps/web/site/assets/*-page.mjs` browser pillars (static site is not prod), ingest scripts, Postgres `scenario_kind`, domain-schema `MetricKind`, `lm_run`, CLI. Loaders may be duplicated per language; lists may not.
**Size:** part of the story.
**Why:** nine fields is the minimum that lets `db.py`, `main.py`, `home-client.tsx` and `engine.ts` all stop knowing any id by name.

## D3 — The two rows

**Decision (rows, exactly):**
- `music` — name `Music`, glyph `♩`, desc `text → music · song gen`, modality `audio`, storable true, metric `{audioXReal, "×real", "realtime", true}`, forbidden `["tokSOutMedian"]`, classify `musicgen|magnet|jasco|ace-?step|\byue2?\b|diffrhythm|stable audio|text-?to-?music|text2music`. Correction to the ask: no `rtf` display fallback. `rtf` is normalized to `audioXReal` at ingest when a real JSONL exists; display code never inverts.
- `image-to-3d` — name `Image → 3D`, glyph `◈`, desc `image → 3D asset`, modality `3d` (root; sibling of the others, not under `image`), storable true, metric `{secPerAsset, "s/asset", "per asset", false}`, forbidden `["tokSOutMedian"]`, classify null (a 3D model row enters via explicit ingest, never by regex). Peak VRAM stays `peakVramGb`, opt-in detail, never headline.
- `audio` gains classify `whisper|wav2vec|audiogen|speech-to-text|\bstt\b|\btts\b`; `code` keeps `coder|starcoder|codestral|code`; `chat` is `fallbackIntent`; `image`/`video` classify null.
- `vision` — modality `text`, storable false, metric tok/s, listed and disabled. Chat/code metric `{tokSOutMedian, "tok/s", "decode", true}`; `metricOf` returns null for modality `text` so callers keep decode tok/s.
No pool cell for music or image-to-3d. No intake submit.
**Size:** part of the story.
**Why:** intent and modality are separate columns now, so "music is an intent of audio" and "image-to-3d is a root" are both one row without a comment.

## D4 — PR #11

**Decision:** Supersede. Replay its music row (glyph, desc, regexes, audio/music split) onto the catalog on a fresh branch off `main`. Do not merge, rebase or cherry-pick PR #11; leave the draft open untouched; the owner closes it after S37 merges. v3 D4 precondition 3 ("finish PR #11 as-is") is superseded by this record.
**Size:** line.
**Why:** the taxonomy in PR #11 is right; its mechanism is the thing being replaced.

## D5 — Run storage

**Decision:** `lm_run.tok_s_out NOT NULL` stays. Music and image-to-3d are `lm_model` categories and UI intents with the existing empty state; they are not runs in SQLite. Postgres `scenario_kind`, domain-schema `MetricKind`, public-api, intake-worker: untouched. Ranking code is not changed for `higherIsBetter: false`; instead a guard test asserts every category present in committed derived JSON has `higherIsBetter: true`, so the first sec/asset cell turns the guard red and forces the ranking story before it can ship.
**Size:** line + one test.
**Why:** a multimodal run shape is a separate story; a guard expresses the precondition mechanically instead of as a schedule.

## D6 — Data honesty

**Decision:** Rejected this turn: MusicGen/A10G numbers in any derived JSON; rig3d timings, VRAM, sha256s or `bestmodel-intake/submission.json`; any invented `n`; enabling static-site pillars; `rtf` inversion in display; `GET /v1/intents`; ranking changes; plausibility changes; `check.py`/`check.mjs` edits; EXL3/RAM/gauntlet (other repo). Fixture values in tests are `1.0` placeholders tagged `fixture_stub`.
**Size:** rejection list.
**Why:** both sessions refused to invent; the catalog must not become the pretext.

## D7 — Story id, paths, acceptance

**Decision:** Spec `specs/en/S37-intent-catalog.md`. S37, not S29: v3 already recorded one id reuse (S30) turning into a STALE row; the highest free id cannot collide with S32–S36 branches. The presence check: a pytest builds `<tmp>/catalog.json` = real catalog + fixture row `zz-fixture` (modality `video`, storable, metric `zzPerSec`, classify `zz-fixture-model`), sets `BESTMODEL_INTENT_CATALOG`, and asserts: `category_check_sql()` contains `'zz-fixture'`; `migrate()` on a temp DB accepts an `lm_model` insert with `category='zz-fixture'`; `classify("ZZ-Fixture-Model 7B","x/y") == "zz-fixture"`; `GET /v1/models?category=zz-fixture` → 200 `{"models": []}` and `?category=nope` → 422; the Node loader returns the same storable set and classification. Without the env var, `zz-fixture` appears nowhere. Re-introducing a literal tuple in `main.py`, `db.py`, `sync_pool.py` or the JS loader turns this red. web-next weakest accepted check: `tsc --noEmit` plus a catalog-derived tripwire (no `id: "<id>"` row literal in `home-client.tsx`, no non-text `metric.unit` literal in `engine.ts`, both import from `lib/intents`).
**Size:** part of the story.
**Why:** the check must exercise the two sites that stopped both sessions, on a real SQLite file and a real route, not on a fake.

## D8 — Order against v3

**Decision:** Replace v3 row 7. Catalog now, in parallel with v3 rows 0–6 (pure code + tests, no prod ops). Music cell and image-to-3d cell become precondition-gated rows, not dates.
**Size:** table below.
**Why:** v2 rule — preconditions, not schedules.

## Order

| # | Item | Size | Precondition |
|---|---|---|---|
| 1 | **S37 intent catalog** (this story) | story M | none — runs now, alongside v3 rows 0–6 |
| 2 | Owner closes PR #11; POINTERS marks v3 D4.3 superseded | lines | S37 merged |
| 3 | Music cell in web-next derived pool via ingest (`rtf`→`audioXReal`, real `n`, real peak VRAM) | story S + ops | a measured music JSONL committed in this repo |
| 4 | image-to-3d cell | story S + ops | ranking honors `higherIsBetter` (D5 guard green) **and** owner copies rig3d evidence into this repo **and** cells go to the derived pool, not `lm_run` |
| 5 | S26 modality registry seeds from `catalog.json` | large, spec first | per v2 order |

## H1+

- **H1:** web-next imports a JSON outside `apps/web-next`; Vercel root-directory scoping or Turbopack root may reject it. Oracle is the PR's Vercel check; fix is `outputFileTracingRoot`/Vercel "include files outside root", never a copied file.
- **H2:** `apps/web/site/assets/*.mjs` almost certainly carries browser-side twins of pillars and possibly `metricOf`; they stay handwritten and will drift until the static site is retired.
- **H3:** Python `re` vs JS `RegExp` dialect drift on `classify`; patterns restricted to alternation, `\b`, `?`; parity test pins the handoff's canonical names.
- **H4:** `lm_model` rebuild runs against the owner's real pool SQLite on first `migrate()`; back up the file before running sync after merge (ops line, owner).
- **H5:** Showing selectable `Music` and `Image → 3D` chips with zero cells can be read as "measured"; the empty-state copy already says "absence, not a zero" — keep it verbatim.
- **H6:** If pool-backend tests are not in CI, the presence check is executor discipline only; the root test therefore spawns the pool-backend suite so `make test`/CI carry it.
- **H7:** Merging PR #11 after S37 would reintroduce `category.py`/`category.mjs`; row 2 above exists for that reason.
- **H8:** `packages/` is documented as Python-only; a JSON-only package needs its own `AGENTS.md` or the next agent moves it.

## Spec skeleton

**Spec:** `specs/en/S37-intent-catalog.md` (executor writes it first, from this section, then code).

**Objective:** Adding an intent to bestmodel is one row in `packages/intent-catalog/catalog.json`; SQLite CHECK, API filter, sync/derive classifier, web-next intent list, `multimodal` flag and `metricOf` all derive from it; a test fails if any of those sites regains a hand list.

**Non-goals:** any measured cell; `lm_run` shape; Postgres/domain-schema; ranking direction; static-site pillars; ingest scripts; `check.py`/`check.mjs`; PR #11 merge; `GET /v1/intents`; rig3d.

**Deliverable paths (exact):**
- `packages/intent-catalog/catalog.json` — 8 rows per D3, order: chat, code, image, audio, music, video, image-to-3d, vision.
- `packages/intent-catalog/AGENTS.md` — "add an intent" checklist (≤ 10 lines) + LOAD-BEARING note naming the tests; `packages/AGENTS.md` gains one row.
- `apps/pool-backend/src/intents.py` — loader: `catalog_path()` (env `BESTMODEL_INTENT_CATALOG` else `Path(__file__).resolve().parents[3]/"packages/intent-catalog/catalog.json"`), `load()` (no module-level cache; read per call), `storable_categories()`, `category_check_sql()` → `CHECK(category IN ('chat','code','image','audio','music','video','image-to-3d'))`, `classify(display_name, hf_id)`.
- `apps/pool-backend/src/db.py` — DDL built at call time from `category_check_sql()`; `migrate()` rebuilds `lm_model` (new table, copy, drop, rename, one transaction, `PRAGMA foreign_keys=OFF` inside, `foreign_key_check` clean after) when `sqlite_master.sql` for `lm_model` lacks the current CHECK string; idempotent.
- `apps/pool-backend/src/main.py` — `list_models` 422 iff `category not in storable_categories()` evaluated per request.
- `apps/pool-backend/src/sync_pool.py` — `model_category` replaced by `intents.classify(display_name, hf_id)`.
- `apps/pool-backend/CONTRATO-GLOBAL.md` — line 64 becomes the generated CHECK string + one sentence pointing at the catalog.
- `apps/pool-backend/tests/test_intent_catalog.py` — real-catalog assertions (music/image-to-3d → 200 empty, vision/nope → 422, contract doc contains `category_check_sql()`), fixture-catalog presence test per D7, legacy-DDL rebuild test (`('chat','code')` DB with one model + rig + run → migrate → `music` insert ok, run count 1, `foreign_key_check` empty, second `migrate()` no-op), Python↔Node classifier parity on: MusicGen, MAGNeT, ACE-Step, YuE, DiffRhythm, Stable Audio → music; Whisper Large v3, faster-whisper, AudioGen → audio; Qwen2.5-Coder, Codestral → code; Llama-3-8B → chat. `pytest`, `httpx` added to pool-backend dev deps if absent; temp DB wired through whatever `src/config.py` already reads, adding an env override there if none exists.
- `apps/pool-backend/AGENTS.md` — one row: reads the catalog by path; still imports nothing from `apps/`/`packages/`.
- `apps/web/scripts/intent-catalog.mjs` — Node loader (`readFileSync`, same env/path rule via `import.meta.url`), exports `INTENTS`, `STORABLE_CATEGORIES`, `classifyModel(display, hfId)`.
- `apps/web/scripts/derive.mjs` — line 143 uses `classifyModel`.
- `apps/web/tests/intent-catalog.test.mjs` — loader reads env override; fixture row present under override and absent without; parity names above.
- `apps/web-next/lib/intents.ts` — `import catalog from "../../../packages/intent-catalog/catalog.json"`; exports `INTENTS` (`{id,name,glyph,desc,category: storable ? id : null}`), `intentOf(id)`, `isMultimodal(id)` (= `modality !== "text"`), `type IntentId`.
- `apps/web-next/lib/engine.ts` — `Cell.category?: IntentId`; `metricOf` = lookup row → null if none or modality `text` → read `cell[row.metric.field]` → `{value, unit, label, higherIsBetter}`.
- `apps/web-next/app/home-client.tsx` — delete local `INTENTS`; import from `@/lib/intents`; line 108 uses `isMultimodal`.
- `tests/test_intent_catalog.py` (root) — catalog well-formed (fields/types, unique kebab ids, modality in `modalities`, `fallbackIntent` is a storable text row, `classify` compiles); derived-JSON guards over `apps/web/data/derived/models.json` and `apps/web-next/public/data/derived/*.json` (every category storable; no `forbiddenFields` on cells; every category with cells has `higherIsBetter: true`); web-next tripwire per D7; one test that runs `uv run --project apps/pool-backend pytest -q tests/test_intent_catalog.py` with `cwd=apps/pool-backend` and fails (not skips) if `uv` is missing.
- `tests/AGENTS.md`, root `AGENTS.md` status line, `docs/POINTERS.md` (new job card `add-intent`: OPEN `packages/intent-catalog/AGENTS.md` + `specs/en/S37-intent-catalog.md`; row marking v3 D4.3 superseded), `docs/direction-2026-09-21.md` (this record, verbatim).

**Requirements the executor must hit:**
1. No file outside `packages/intent-catalog/catalog.json` contains a list of intent ids; loaders contain logic only.
2. No import from `apps/` or `packages/` inside `apps/pool-backend/`; file read by path only.
3. Both new intents render as selectable chips with the existing empty-state copy; vision unchanged.
4. No derived JSON, seed, fixture or doc gains a music or 3D number; fixtures use `1.0` and `sourceClass: fixture_stub`.
5. Mutation check, run once and reported in the PR description, not committed: replace `storable_categories()` in `main.py` with a literal tuple → `apps/pool-backend/tests/test_intent_catalog.py` must go red.
6. If Next/Vercel rejects the out-of-root JSON import, fix via `outputFileTracingRoot`/Vercel setting; never copy the catalog.
7. Conventional commits per logical change: `feat(S37): ...`, `docs(S37): ...`. Branch off `main`; PR #11 untouched.

**Acceptance commands (exact, all green, run from repo root):**
```bash
uv run pytest tests/test_intent_catalog.py -q -rs          # 0 skipped
(cd apps/pool-backend && uv run pytest -q tests/test_intent_catalog.py)
node --test apps/web/tests/intent-catalog.test.mjs
(cd apps/web-next && npx tsc --noEmit)
make test
```
Plus: the PR's Vercel check green (build oracle for H1), and the mutation check in requirement 5 observed red then reverted.

EXECUTOR: IMPLEMENT THIS STORY
