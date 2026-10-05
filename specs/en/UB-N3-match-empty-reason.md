# Task: POST /v1/match/hardware-to-models explains an empty answer

OBJETIVO: when the match returns no candidates, say why and what valid input looks like, so an agent can recover in one call. Work only in apps/public-api (plus its tests). Local commits fine, never push.

## Dados verificados
- `apps/public-api/src/services/query_hardware_match.py`: returns `{"matches": []}` both when no GPU id is known (`fetch_gpus_by_ids` empty) and when the family has no models (loop over `fetch_models_by_family` yields nothing). Callers cannot tell the two apart.
- 2026-10-05: a real call with `gpu_model_ids=["gpu-rtx-3090"]`, `target_model_family="qwen"` returned `{"matches": []}` with no hint.
- `DatabaseSession` (src/dependencies/database_session_provider.py) already has `fetch_all_gpus()` and `fetch_all_models()`; the fake (`packages/fake-adapters/src/fake_database.py`) implements both. Models rows carry `family`.
- Tests: `cd apps/public-api && uv run --with pytest --with httpx pytest -q` (5 match tests pass today). `test_unknown_gpu_ids_return_empty_matches` asserts `== {"matches": []}` and must be updated, not deleted.

Nao invente numero, prazo ou fonte alem dos listados.
NUNCA use declare const como workaround — importe de verdade.

## PROIBIDO
push. deploy. Changing the 200 status code or the shape of a non-empty `matches` item. Editing other routes. Portuguese in code, comments or messages. Adding a DB method that the real adapter does not implement.

## PASSOS
1. In `query_hardware_matches`, when the result is empty, return `{"matches": [], "reason": <code>, "detail": <English sentence>, ...hints}`:
   - `unknown_gpu_model_ids`: some requested ids are not in `fetch_all_gpus()`. Hints: `unknown_gpu_model_ids` (sorted list) and `valid_gpu_model_ids` (sorted, max 50, prefer ids sharing a token with the unknown ones, e.g. `gpu-a100` → ids containing `a100`).
   - `unknown_model_family`: GPUs known, family has no models. Hints: `valid_model_families` (sorted unique `family` values from `fetch_all_models()`, max 50) and `closest_model_families` (up to 5 whose name contains the requested string or vice versa).
   - `no_feasible_candidate`: models existed but every candidate raised ValueError. Hint: `skipped_candidates` count.
2. Non-empty responses stay exactly `{"matches": [...]}` (no new keys).
3. Tests in `tests/test_hardware_match_route.py`:
   - unknown id → `reason == "unknown_gpu_model_ids"`, the bad id listed, `valid_gpu_model_ids` non-empty.
   - unknown family → `reason == "unknown_model_family"`, `valid_model_families` contains `qwen-2.5-coder`.
   - family `"qwen"` → `closest_model_families` contains `qwen-2.5-coder`.
   - the existing non-empty test still asserts the exact field set.

VERIFICACAO: cd apps/public-api && uv run --with pytest --with httpx pytest -q

## Oraculo
- comando: cd apps/public-api && uv run -q --with pytest --with httpx pytest -q && grep -q "unknown_model_family" src/services/query_hardware_match.py && grep -q "closest_model_families" tests/test_hardware_match_route.py
- exit esperado: 0

## Barra
- nome: public-api pytest
- como fetchar: cd apps/public-api && uv run --with pytest --with httpx pytest -q
- como comparar: whole suite green, new reason tests present
