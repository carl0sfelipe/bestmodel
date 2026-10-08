# S49 — `GET /v1/pick`: best model per intent and VRAM (contract model-pick-v1)

> Source: `carl0sfelipe/hq` → `contracts/model-pick-v1.md` (producer: bestmodel,
> consumer: llms-surf-cloud). Depends on S48 (match honesty).

## Objective

An outside agent asks "which model for intent X fits Y GiB on rig Z?" in one
call to the documented host, and every answer row declares its confidence.

## Verified data (2026-10-08)

- `llms.txt` listed the API routes without a host; `https://www.bestmodel.run/v1/leaderboard`
  answers 404 HTML, `https://api.bestmodel.run/v1/leaderboard` answers 200.
  Command: `curl -sS -o /dev/null -w "%{http_code}" https://www.bestmodel.run/v1/leaderboard`
- Production leaderboard holds 1 validated run on the 3090. Command:
  `curl -sS "https://api.bestmodel.run/v1/leaderboard?gpu_model_id=gpu-rtx-3090&limit=100"`
- Pool snapshot `apps/web/data/derived/pool.json` (snapshotAt 2026-09-18) has 85
  cells on `rtx-3090-24gb`: 84 chat, 1 code, 0 image/vision/audio. All 686 models
  carry `sourceClass: community_reported`.

## Contract

1. `apps/public-api/src/services/model_pick.py` + `routes/model_pick_route.py`:
   `GET /v1/pick?intent=&vram_gib=&gpu=[&limit=]`. Intents `chat`, `image.generate`,
   `vision`, `audio` map to intent-catalog ids. `gpu` is a snapshot rig key.
2. Rows: cells on the rig, model category = intent, `peakVramGbMedian ≤ vram_gib`
   (unknown peak is excluded). Rank: confidence, pool eval score (missing last), speed.
3. Confidence: `community_reported` → `reported`; anything else → `no data yet`.
   Never `measured` from the snapshot.
4. No cell → `picks: []`, `confidence_floor: "no data yet"`. Unknown intent/rig → 400.
5. `infra/docker/api.Dockerfile` copies `apps/web/data/derived/`.
6. `llms.txt` (root, `apps/web/site`, `apps/web-next/public`) declares the API host
   and `/v1/pick`.

## Rules

- Gate clause: do not invent a number, metric or copy beyond the ones listed in
  Verified data; missing data renders as "no data yet".
- Gate clause: never use declare const, a stubbed success or a fake badge as a
  workaround — implement the real capability.
- Unmeasured candidates (Bonsai 2.0, Ornith 1.5) get no cell until signed
  measurements arrive through the intake flow.

## Acceptance (each criterion = one command)

1. Route contract: `uv run pytest -q apps/public-api/tests/test_model_pick_route.py`
2. Suite green: `make test`
3. E2E: `make gate`
