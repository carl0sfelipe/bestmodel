# S37: Intent catalog

Implements `docs/direction-2026-09-21.md`. Adding an intent is one row in
`packages/intent-catalog/catalog.json`. The SQLite CHECK, the API category
filter, the sync/derive classifier, the web-next intent list, the multimodal
flag and `metricOf` all derive from that file.

## Objective

A new intent does not require a sweep of allowlists. A test fails if
`db.py`, `main.py`, `sync_pool.py`, the JS loader, `home-client.tsx` or
`engine.ts` grows a handwritten list of intent ids again.

## Non-goals

Measured cells of any kind. `lm_run` shape (`tok_s_out` stays `NOT NULL`).
Postgres `scenario_kind` and domain-schema `MetricKind`. Ranking direction.
Static-site pillars (`apps/web/site/assets/*-page.mjs`). Ingest scripts.
`scripts/check.py` and `apps/web/scripts/check.mjs`. Merging PR #11.
`GET /v1/intents`. Anything in the rig3d repo.

Handwritten on purpose, until a later story: browser pillars, ingest, the
signed-run contract, CLI.

## Deliverables

See the path list in `docs/direction-2026-09-21.md` § Spec skeleton. That
list is the contract for this story.

Rows, in file order: chat, code, image, audio, music, video, image-to-3d,
vision. `music` is modality `audio`. `image-to-3d` is modality `3d` (a root,
not a child of `image`). `vision` is listed and `storable: false`.

## Requirements

1. Loaders contain logic only. The id list lives in `catalog.json`.
2. `apps/pool-backend` reads the catalog by path (`BESTMODEL_INTENT_CATALOG`
   or the repo-relative default). It does not import `apps/` or `packages/`.
3. Music and Image → 3D are selectable chips. The existing empty-state copy
   stays verbatim. Vision stays `category: null` and disabled.
4. No derived JSON, seed, fixture or doc gains a music or 3D measurement.
   Test placeholders are `1.0` with `sourceClass: fixture_stub`.
5. `metricOf` returns null for modality `text`. It never inverts `rtf`.
6. `lm_model` rebuilds when the stored CHECK lacks the current catalog
   string. The rebuild is one transaction, foreign keys off for the swap,
   `foreign_key_check` clean after, and a second `migrate()` is a no-op.

## Acceptance

From the repo root, all green, zero skipped:

```bash
uv run pytest tests/test_intent_catalog.py -q -rs
(cd apps/pool-backend && uv run pytest -q tests/test_intent_catalog.py)
node --test apps/web/tests/intent-catalog.test.mjs
(cd apps/web-next && npx tsc --noEmit)
make test
```

Mutation check (not committed): a literal category tuple in
`list_models` must turn `apps/pool-backend/tests/test_intent_catalog.py` red.
