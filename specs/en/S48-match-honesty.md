# S48 — Match honesty: source class on every row, no incompatible runtime

> Source: outside-agent probe of api.bestmodel.run on 2026-10-08 (owner request,
> `carl0sfelipe/hq` → `contracts/model-pick-v1.md`, blocker rows 6). First of two
> PRs; `/v1/pick` (contract model-pick-v1) is S49 and depends on this.

## Objective

Every row returned by the two match routes declares where its number came from,
and no row pairs a text model with an engine that cannot serve it.

## Verified data (2026-10-08)

- `POST /v1/match/hardware-to-models` with `target_model_family=gemma` on
  `gpu-rtx-3090` returns 100 rows; the first is `model-gemma-4-26b-a4b-it` /
  `q-gguf-q2-k` / `runtime_id: comfyui` with `expected_decode_tok_s: 549.4` and
  **no `source_class`**. Command: `curl -sS -X POST https://api.bestmodel.run/v1/match/hardware-to-models -H 'content-type: application/json' -d '{"gpu_model_ids":["gpu-rtx-3090"],"gpu_count":1,"ram_gib":64,"os_name":"linux","target_model_family":"gemma","target_context_tokens":8192}'`
- Both services loop every row of `inference_runtime`, and the seed includes
  `comfyui` (diffusion; migration 0011).
- Both services compute roofline estimates only; `source_transparency.py`
  names that class `derived`.

## Contract

1. `apps/public-api/src/services/match_honesty.py`: `MATCH_SOURCE_CLASS = "derived"`
   and `TEXT_GENERATION_ENGINES` (every `RuntimeEngine` except `comfyui`).
2. `query_hardware_match` and `query_model_match` evaluate only text-generation
   runtimes and add `source_class` to every row. Additive field; §9.4 names unchanged.

## Rules

- Gate clause: do not invent a number, metric or copy beyond the ones listed in
  Verified data; missing data renders as "no data yet".
- Gate clause: never use declare const, a stubbed success or a fake badge as a
  workaround — implement the real capability.
- A derived value never claims `measured_signed`.
- A new `RuntimeEngine` must be classified on purpose (unit test fails otherwise).

## Acceptance (each criterion = one command)

1. Rows carry `source_class` and no comfyui: `uv run pytest -q apps/public-api/tests/test_hardware_match_route.py apps/public-api/tests/test_model_match_route.py`
2. Every engine classified: `uv run pytest -q apps/public-api/tests/test_match_honesty.py`
3. Suite green: `make test`
4. E2E: `make gate`
