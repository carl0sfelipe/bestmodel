# Run Luna Catalog Report

## Story 1

- Added `fetch_all_model_releases` to the abstract database session and to the Postgres and fake adapters.
- Added public `GET /v1/model-releases` and `GET /v1/quantization-profiles` routes with explicit projections, envelopes, ordering, and Decimal-to-float conversion.
- Registered the catalog router before `claim_route`.
- Added route tests covering public access, counts, exact item keys, required seed records, and ordering.
- Verification: `uv run pytest apps/public-api/tests/test_catalog_routes.py -q` passed; `uv run pytest tests/test_session_contract.py -q` passed.

## Story 2

- Added typed catalog API calls in `apps/web-next/lib/social.ts` using the existing `request` helper.
- Added an API-first catalog loader with the required feed-derived fallback.
- Updated the capture form to retain catalog objects, use authoritative API names, preserve derived modality grouping, label quantizations with `display_name`, and show provenance-specific help text.
- Verification: `npm --prefix apps/web-next run build` passed.

## Story 3

- Skipped because `docs/en/api.md` does not exist on disk. No documentation file was created.

## Divergences

- The spec says no method returning all `model_release` rows exists, but the disk already contains `fetch_all_models` in `apps/public-api/src/dependencies/database_session_provider.py:280` and its implementations in `apps/public-api/src/dependencies/database_session_provider.py:896` and `packages/fake-adapters/src/fake_database.py:574`. Per the protocol, these existing methods were preserved; the requested `fetch_all_model_releases` method was added alongside them.
- The spec says the fake follows database ordering, but its existing catalog methods return seed order at `packages/fake-adapters/src/fake_database.py:120` and `packages/fake-adapters/src/fake_database.py:129`. The public route sorts by `id` explicitly in `apps/public-api/src/routes/catalog_route.py:28` and `apps/public-api/src/routes/catalog_route.py:45` so the HTTP contract remains correct.
- The spec places the session contract test under `apps/public-api/tests`, but the repository contains it at `tests/test_session_contract.py`.
- The stated expected Next version is 15, while the build output reports Next.js 15.5.2.

## Not Done

- No database migration was created or changed.
- No existing route, validation, submission behavior, auth, cache, pagination, or port configuration was changed.
- No `git push` was run.
