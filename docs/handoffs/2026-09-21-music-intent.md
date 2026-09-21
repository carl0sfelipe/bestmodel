# Handoff — music intent (2026-09-21)

Source session: cloud agent that opened draft PR #11. This file is a dump, not a new change. Do not treat it as implementation.

DISCORDÂNCIA with the briefing facts: none. Precisions that the briefing compressed are marked PRECISION below.

Receiver note (this monorepo, 2026-09-21): the source session left this file uncommitted on its own VM. It is copied here as the Clarify input for the 2026-09-21 escalation. It is not the music implementation.

## 1. Session

- Branch: `cursor/music-intent-from-audio-d6bb`
- HEAD: `e33b1eaee80171bbc2a0fc1902526e5b06ed4b37`
- Parent commits on this branch, oldest first:
  - `a4ca3da` feat: add music intent nested under the audio modality
  - `e33b1ea` test: fix music fixture path from apps/web tests
- Base: `main` at `df736bd` (ci: remove backup-alarm).
- `git status --short` at dump time, before this file existed: empty. Working tree was clean. No uncommitted music diff. No uncommitted diff to paste.
- This handoff file is the only file written by the dump. It is intentionally uncommitted on the source VM. Do not commit it as part of the music work unless a human asks.
- Draft PR: https://github.com/carl0sfelipe/bestmodel/pull/11 (not merged).
- CI on `e33b1ea`: all 6 checks completed without failures (python, rust-cli, Vercel). Reported by the GitHub CI subscription after the PR was opened.
- Vercel preview was Ready and login-gated: `https://bestmodel-next-git-cursor-music-i-9ec027-carl0sfelipes-projects.vercel.app`

## 2. Definição fechada

- id: `music`
- UI name: `Music`
- web-next glyph/desc: `♩`, `text → music · song gen` (`apps/web-next/app/home-client.tsx`)
- Physical modality: `audio`. `INTENT_MODALITY["music"] == "audio"`. Same waveform domain as `audio`. Not a third LLM intent beside `chat` / `code`.
- What lands as `music`: text-to-music / song gen. Classification regex (display name or hf id): MusicGen, MAGNeT, JASCO, ACE-Step / ACEStep, YuE / YuE2, DiffRhythm, Stable Audio, plus the phrases `text-to-music` / `text2music`.
- What stays `audio` (STT / TTS / SFX, not song gen): Whisper, faster-whisper, distil-whisper, wav2vec, AudioGen, speech-to-text, STT, TTS.
- What stays `code` / `chat`: the old coder/starcoder/codestral/code heuristic, then default `chat`. Chat and code were not removed.
- Out of this intent: vision (`category: null` in the web-next intent list; the chip stays disabled, “no community data yet”). AudioGen is SFX, so it stays `audio`, not `music`. SAM Audio / stem separation was in the queue notes as not generation; this session did not add a category for it.
- 3D gen: ABSENT. This conversation never designed a 3D intent.

PRECISION: on the branch the SQLite CHECK is not a hardcoded string inside `db.py`. `MODEL_CATEGORIES = ("chat", "code", "image", "audio", "music", "video")` and `category_check_sql()` builds the tuple. `apps/pool-backend/CONTRATO-GLOBAL.md` does contain the literal `CHECK(category IN ('chat','code','image','audio','music','video'))`. On `main`, `apps/pool-backend/src/db.py` is still `CHECK(category IN ('chat','code'))`. Confirmed with `git show main:apps/pool-backend/src/db.py`.

PRECISION: web-next Music is selectable. The static site (`apps/web`) lists Music but `enabled: false` until that pool slice has community cells.

## 3. Mapa de limites

| Lock | File | Restriction found | Wanted change | Where it stands |
|---|---|---|---|---|
| SQLite CHECK | `apps/pool-backend/src/db.py` | `category IN ('chat','code')` on main. SQLite cannot ALTER a CHECK. | Accept `music` and `audio`, and the other multimodal intents already used by web-next (`image`, `video`). | On the branch. New DBs get the wide CHECK. Existing DBs rebuild `lm_model` when the stored SQL lacks `'music'` and `'audio'`. |
| Contract DDL | `apps/pool-backend/CONTRATO-GLOBAL.md` | Same `('chat','code')` literal. | Document intent vs modality and the wide CHECK. | On the branch. |
| API filter | `apps/pool-backend/src/main.py` `GET /v1/models?category=` | Rejected anything other than `chat`/`code` with 422. | Accept every `MODEL_CATEGORIES` value; 422 on unknown. | On the branch via `validate_category_filter`. Empty `music` list is a 200, not a fake row. `scripts/check.py` asserts `music` and `audio` return 200 and a bogus category returns 422. That oracle was not executed here (no synced SQLite pool, no FastAPI in the VM). |
| Derive | `apps/web/scripts/derive.mjs` | `/coder\|starcoder\|codestral\|code/i` else `chat`. | Shared `modelCategory(display, hfId)`. | On the branch. `scripts/check.mjs` rejects a derived category outside `MODEL_CATEGORIES`, and rejects a multimodal cell that carries `tokSOutMedian`. Not run against `data/derived` in this session. |
| Sync | `apps/pool-backend/src/sync_pool.py` | Local `model_category()` was code-else-chat, display name only. | Import `model_category(display, hf_id)` from `src/category.py`. Music before audio before code/chat. | On the branch. Live localmaxxing sync was not run. |
| JS twin | `apps/web/scripts/category.mjs` | ABSENT before this session. | Lockstep with the Python taxonomy. | On the branch. |
| UI intents, web-next | `apps/web-next/app/home-client.tsx` | Six intents; audio was STT; no music. Vision `category: null`. | Add Music (`category: "music"`). Treat music as multimodal (no context-floor, no bits). Vision stays null and disabled. | On the branch. |
| UI pillars, static site | `apps/web/site/assets/hardware-page.mjs`, `goal-page.mjs`, `mobile-page.mjs` | Pillars/outputs were chat, code, image, audio, video, vision. Disabled pillars had no pool. | List Music. Leave `enabled: false`. Goal/mobile `currentCategory()` maps output `music`/`audio` when those chips are used. | On the branch. Pillars stay disabled. |
| Metric | `apps/web-next/lib/engine.ts` `metricOf` | Audio only if `category === "audio"` and `audioXReal` set. | `audio` and `music` share ×real. If the cell has `rtf` (wall/audio) and no `audioXReal`, invert to ×real (`1/rtf`) for ranking. Image/video unchanged. Text still returns null so callers keep `decode_tok_s`. | On the branch. |
| Ingest | `ingest.py`, `ingest_anchors.py` | Metric keys were `imagesPerSec`, `audioXReal`, `videoFramesPerSec`. Whisper hard-coded as `audio`. | Also accept `rtf`. Comment: do not insert MusicGen into `new_models` without a measured JSONL. | On the branch. No JSONL was ingested. No pool JSON was rewritten. |
| `lm_run` shape | `apps/pool-backend/src/db.py` | `tok_s_out REAL NOT NULL`. Runs are text speed-tests. | A music cell must not be forced through decode tok/s. | NOT DONE. Category can be `music` on `lm_model`, but a music measurement still cannot be an `lm_run` row without inventing `tok_s_out`. Left that way on purpose. |
| Domain schema / Postgres | `packages/domain-schema`, `apps/public-api`, `infra/migrations` | Frozen report contract. No pool-category CHECK there. | Do not rewrite the modality registry or the signed-run contract for this. | NOT DONE. ABSENT from the PR. |
| Static derived JSON | `apps/web/data/derived/models.json`, `apps/web-next/public/data/derived/*` | Shipped pool is chat/code plus existing multimodal anchors (Whisper is already `audio` with `audioXReal` in web-next pool). | Do not invent a MusicGen cell in those files. | NOT DONE. No music model/cell was added to derived JSON. |

## 4. O que entrou no PR

- Taxonomy module `apps/pool-backend/src/category.py` and `apps/web/scripts/category.mjs`.
- CHECK widen + rebuild in `db.py`. Contract text in `CONTRATO-GLOBAL.md`.
- API validation, sync classification, derive classification, web `check.mjs` category guard, pool-backend `check.py` assertions for `?category=music` and `?category=audio`.
- `metricOf` music path (`audioXReal` or inverted `rtf`). Ingest accepts `rtf`.
- web-next Music chip (selectable, multimodal). Static-site Music entries (listed, disabled).
- Tests: `tests/test_music_intent.py` (21 passed under `python3 -m pytest` after a local pytest install). `apps/web/tests/category.test.mjs` plus existing `engine.test.mjs` and `claims-tier.test.mjs` passed under `node --test`.
- Fixture: `tests/fixtures/music_audio_intent.json`.
- Docs touched: `AGENTS.md` status line, `apps/pool-backend/AGENTS.md`, `docs/architecture.md` short “intents vs modalities” note, `tests/AGENTS.md`.
- Second commit only fixes the fixture path in the JS test (`../../../tests/fixtures/...` from `apps/web/tests`).

## 5. O que ficou de fora e por quê

- Measured MusicGen / A10G numbers. The upload `result-music-a10g.json` was shape reference. Copying it into `pool.json` would publish a measurement this session did not re-run or sign. Forbidden by the task.
- Modal upload or signing. Explicit non-goal.
- Enabling the static-site Music pillar. `apps/web` derived data is the localmaxxing text pool. Enabling it would advertise a category with no cells there.
- Inserting MusicGen into `ingest_anchors.py` `new_models`. Comment in that file says not to, without a measured JSONL.
- Changing `lm_run.tok_s_out NOT NULL`, plausibility (roofline is tok/s), or match ranking so music participates in hardware-to-models. Those paths are still text. A music model row can exist; a music run cannot, honestly, until the run table grows a multimodal shape.
- `packages/domain-schema` `MetricKind` and public-api Postgres. Out of scope; the pool category lives in the SQLite pack and the derived JSON.
- Vision category. Still null. No collection plan in this session.
- 3D gen. ABSENT.
- `make gate`, `make test` via uv, `scripts/check.py match|derived|sync`. The VM had no `uv` and no FastAPI. Those oracles need the synced SQLite pool. Not faked.

## 6. Contrato de métrica e o que é proibido mostrar

Music and audio cells use the multimodal path:

- Preferred stored field already in the pool: `audioXReal` (×realtime). Unit shown: `×real`. Label: `realtime`.
- Music measurement shape from the A10G notes: `rtf` = wall/audio, plus `wall_s`, `audio_s`, `peak_vram_gb` / `peakVramGb`, `durationS`, `n`. Ranking inverts RTF to ×real (`1/rtf`) so higher is faster. Do not display that inverted value as if it were a measured tok/s.
- Peak VRAM stays peak VRAM. It is not a speed.
- Forbidden on a music or audio cell: `decode_tok_s`, `tokSOutMedian` as the headline, prefill tok/s, TTFT-as-the-answer. `apps/web/scripts/check.mjs` fails a multimodal cell that carries `tokSOutMedian`.
- Text chat/code cells keep `decode_tok_s`. Do not route them through `metricOf`.
- `n` still decides basis (`n >= 3` measured, else reported) via existing `basisOf`. Do not invent `n`.

## 7. Honestidade

- Measured and already in the web-next pool before this session: Whisper Large v3, category `audio`, `audioXReal` (the browser pass reported 4.8 ×real on L4 24GB modal). This session did not create that cell.
- Stub: `tests/fixtures/music_audio_intent.json`. `sourceClass: fixture_stub`. Whisper cell `audioXReal: 1.0`. MusicGen cell `rtf: 1.0`, `peakVramGb: 1.0`, `n: 1`. Placeholders so they cannot be read as the A10G medians.
- The A10G MusicGen JSON (RTF medians, peak VRAM, n=3, `source_class: measured`) was read as shape only. It was not copied into pool JSON, models JSON, seeds, or the fixture.
- INVENTADO: nothing. No measured speed, VRAM, or run count was written into product data.
- Browser pass (subagent, local Next server, because the Vercel preview asked for login): Music selected showed an honest empty state, roughly “No data yet for this combination. Nobody has submitted a music run on CMP 170BX 64GB. That is an absence, not a zero”. Audio still showed Whisper in ×real. Chat and code still showed tok/s. This agent did not click the preview itself. No music number was fabricated in that UI.

## 8. Onde a sessão se perdeu

- The first JS test resolved the fixture to `apps/tests/fixtures/...` (`../../` from `apps/web/tests`). That failed once. Fixed in `e33b1ea`. Not a product bug.
- “End-to-end” is category + API allowlist + derive/sync heuristic + metric function + a stub fixture. It is not a music row in SQLite `lm_run` and not a MusicGen cell in `pool.json`. Easy to over-read the PR as “music is measured in the pool”. It is not.
- `uv` / FastAPI were absent, so `apps/pool-backend/scripts/check.py` (the oracle that hits `/v1/models?category=music` against a real DB) never ran. A throwaway `PYTHONPATH=.` migrate on a temp database did accept `music` and `audio` inserts, including a rebuild from the legacy CHECK.
- Vercel preview was login-gated. UI confirmation was a subagent on localhost, not that URL.
- Time was not spent on vision, 3D, or the frozen benchmark-report contract. Those are still where they were.

## 9. Próximo passo

Leave PR #11 as the category contract (draft until a human marks it ready) and do not merge from this dump. The next implementation session, if it continues music, should ingest a real measured music JSONL through `ingest.py` (category `music`, metric `rtf` or `audioXReal`, real `n`, real peak VRAM) into the web-next derived pool, still without inventing cells, and only then consider enabling the static-site Music pillar. Do not stuff those runs into `lm_run` while `tok_s_out` is NOT NULL. 3D gen stays ABSENT until a separate decision.
