# packages/intent-catalog/ — Map

JSON only. Not a Python package. pool-backend reads this file by path and
does not import it. web-next imports the same file. Do not copy it.

## Add an intent

1. Append one object to `intents` in `catalog.json` (file order is UI order and classify precedence).
2. Run `uv run pytest tests/test_intent_catalog.py apps/pool-backend/tests/test_intent_catalog.py -q` from the repo root, then the pool-backend pytest named in `specs/en/S37-intent-catalog.md`.
3. If the contract test prints a CHECK string, paste that string into `apps/pool-backend/CONTRATO-GLOBAL.md`. Do not edit `db.py`, `main.py`, `home-client.tsx` or `engine.ts` to add the id.

## Load-bearing

LOAD-BEARING: the id list lives only in `catalog.json`. `tests/test_intent_catalog.py` and `apps/pool-backend/tests/test_intent_catalog.py` fail when a consumer hardcodes a category tuple again. `vision` is listed and not storable. `lm_run.tok_s_out` stays NOT NULL; music and image-to-3d are categories, not runs.
