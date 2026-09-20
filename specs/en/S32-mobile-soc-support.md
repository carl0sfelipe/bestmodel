# S32 — Mobile SoC support: phones are rigs (Galaxy S25 Ultra first)

> Origin: owner dogfood request 2026-09-20 ("bought an S25 Ultra — what
> runs on it, how do I use bestmodel.run on it, get the mobile SOTAs on
> the site"). Read-side record with every finding (M1–M14) and every
> vendor number: `docs/QA-MOBILE-DOGFOOD-2026-09-20.md`; incident diary
> entry (workarounds W1–W8 → the story that removes each):
> `docs/incidents/2026-09-20-cli-nao-responde-hardware-fora-do-catalogo-ia-fez-workaround.md`.
> This file is the
> write side: seven independently dispatchable stories (S32a–S32g), each
> with its own frozen oracle, sized for a cheap executor through llms.surf
> (one session · one story · one oracle · one commit `feat(S32x): ...`).
>
> **Não invente número, prazo ou fonte além dos listados em Verified
> data.** Every figure below is either read from this repo at `main`
> `16cf014`, cited to a vendor document, or marked `[A DEFINIR]` until
> measured on the device. NUNCA use `declare const`/stub como workaround
> — coluna ou tabela inexistente se migra, não se declara. Never weaken
> an existing test to make a cut pass. Vendor numbers are **claims**,
> never cells.

## Objective

A person holding a Galaxy S25 Ultra (SM-S938x, Snapdragon 8 Elite for
Galaxy, 12 GB LPDDR5X) opens `www.bestmodel.run` and can: (1) pick — or be
offered — their phone as the machine; (2) see the honest answer for it
(measured/reported cells when they exist, vendor claims labelled as
claims, `formula` fit with the Android-memory caveat, `no data yet`
otherwise); (3) capture a run from a phone app as a claim bound to the
phone's catalog row; (4) eventually produce a **signed** run from Termux
that the worker validates. The pool gains a class of rigs
(`formFactor: phone`) without losing the honesty ladder.

## Verified data (on-disk facts at `main` `16cf014` — the only inputs allowed)

Repo facts:

- Home rig picker: `apps/web-next/app/page.tsx` — `RIG_LIMIT = 24`,
  `topRigs()` sorted by `runCount` desc (`apps/web-next/lib/engine.ts`).
  The two phone-class rigs have `runCount` 1 and 4 → never offered.
- Derived rigs: `apps/web-next/public/data/derived/hardware.json` (185
  rigs, snapshot `2026-09-18T17:08:19.808Z`), byte-copy of
  `apps/web/data/derived/hardware.json`. Rig shape:
  `{key,label,hwClass,memGb,gpuCount,bandwidthGBs,runCount}`;
  `hwClass ∈ {DISCRETE_GPU, UNIFIED, CPU_ONLY}` comes from the upstream
  pool, unchanged by `apps/web/scripts/derive.mjs`.
- Phone-class rigs today: `cpu-qualcomm-snapdragon-888-arm64` (label
  `Qualcomm Snapdragon 888 ARM64`, CPU_ONLY, memGb 12, bandwidth null, 1
  run) and `tecno-pova-7-ultra-5g-mali-g615-mc6-11-23gb` (UNIFIED, memGb
  11.23, bandwidth null, 4 runs). One pool cell on a phone:
  `google-gemma-4-e2b-it`, bits 4, n 1, `tokSOutMedian` 6.2, ttft 10000
  ms, peakVram 6 GB, ctx 1306, engine `llama.cpp`.
- `apps/web/scripts/derive.mjs` needs `data/raw/*` which is **not in git**
  (harvest output). Enrichment must therefore work from the committed
  derived JSON, not from raw.
- `apps/web/scripts/check.mjs`: `DELIVERED` list (line 5) and `TARGETS`
  map (lines 294–297) — the place to register a new target.
- Bandwidth seed: `apps/web/data/seed/bandwidth.json` (name → GB/s, 44
  entries, no SoC). `seedBandwidth()` returns null for CPU_ONLY.
- Agent surface copies: `llms.txt` (root, "Reader journeys"),
  `apps/web/site/llms.txt`, `apps/web-next/public/llms.txt` (lines 8–10
  and 60–61 point at `m/index.html?as=human` and `hardware.html?as=human`,
  both 404 on prod: `/m/[slug]` is the model page; `/hardware` exists,
  `/hardware.html` does not).
- DB catalog: `gpu_model` (migration `0001`): `tdp_watt INT NOT NULL
  CHECK (> 0)`, `memory_bandwidth_gib_s NUMERIC NOT NULL CHECK (> 0)`,
  `vram_mib BIGINT NOT NULL`; 29 seed rows in `infra/seed/gpu_models.json`
  (vendors NVIDIA/AMD/Apple). Convention already in the seed: the column
  named `_gib_s` holds the vendor GB/s figure (RTX 4090 = `1008.0`).
  `packages/domain-schema/src/gpu_spec.py` `GpuSpec.tdp_watt: int =
  Field(gt=0)`. `hardware_class` enum has unused `npu`, `integrated_gpu`.
  Seed loader `infra/seed/load_seed.py` inserts the listed `columns`
  only (`ON CONFLICT (id) DO NOTHING`); FakeDatabase loads
  `gpu_models.json` directly (`packages/fake-adapters/src/fake_database.py`
  line 36) — a new seed row is visible to every Fake-backed test with no
  code.
- Model catalog: 77 rows in `infra/seed/model_releases.json`; ≤ 5 B set is
  qwen2.5 0.5/1.5/3B (+coder), llama-3.2 1B/3B, phi-3 mini ×3, gemma-2
  2B, qwen3.5 0.8B/4B, lfm2.5 350M, r1-distill-qwen 1.5B. Expansion
  mechanism exists: `infra/scripts/expand_catalog_from_hf.py` (S22 —
  specs from HF `config.json`, never invented).
- Claims: `POST /v1/claims`, `CreateRunClaimRequest`
  (`apps/public-api/src/schemas/claim_schemas.py`) accepts
  `model_release_id`, `claimed_metrics`, `rig_slug`,
  `quantization_profile_id`, `inference_runtime_id`, `gpu_model_id`,
  `context_tokens`, `note`, `source_url`. The web form
  (`apps/web-next/app/submit/submit-client.tsx`) sends everything except
  `inference_runtime_id` and `rig_slug`; hardware is a free-text input
  (lines 460–469). Prior: `compute_claim_prior.py` — roofline leg only
  when `gpu_model_id` resolves via `fetch_gpus_by_ids`; a missing prior
  never blocks creation.
- Import pattern: `infra/scripts/import_localmaxxing.py` (`--dry-run` /
  `--apply` / `--source-url` / `--snapshot-at` / `--limit`) →
  `apps/public-api/src/services/import_localmaxxing_claims.py`
  (`external_ref_for`, `find_run_claim_by_external_ref` idempotency,
  `match_gpu` by suffix, `provenance` jsonb from S28 migration `0014`).
- Runtimes: `runtime_engine` enum (`0002`) and `RuntimeEngine`
  (`benchmark_report.py`) = llama_cpp, ollama, vllm, sglang, exllamav2,
  tensorrt_llm, mlx, lmstudio (+ comfyui in Python); pinned exactly by
  `packages/domain-schema/tests/test_enums.py`. Seed
  `infra/seed/inference_runtimes.json` has 5 ids (`llama-cpp`, `ollama`,
  `vllm`, `exllamav2`, `comfyui`).
- CLI: `cli/benchmark-probe/src/collect_system_topology.rs` branches on
  `cfg!(target_os = "macos")` / `"linux"` only (lines 27–63); Rust's
  `aarch64-linux-android` target sets `target_os = "android"`, so every
  detector returns `String::default()` there. Deps (`Cargo.toml`):
  reqwest blocking + `openssl-sys` vendored, ed25519-dalek, argos-opt
  (path). No `sysinfo`/`nvml` crate.
- Worker: `apps/intake-worker/src/postgres_repository.py` line 296 —
  `gpu_model_id = run_row["gpu_model_id"] or UNBOUND_HARDWARE`; an
  unresolved GPU is an existing, handled state.
- canirunit (built and run 2026-09-20 against `pool.json`):
  `suggest --gpu snapdragon-8-elite-12gb --task decode_tok_s --gpus
  cli/canirunit/gpu_transfer_specs.json` → `match_class: unknown`, exit
  3, hint `arc-b580-12gb, cpu-qualcomm-snapdragon-888-arm64,
  rtx-3060-12gb, ...`. `gpu_transfer_specs.json` = 5 entries, ids
  `gpu-rtx-3090|4090|4080|4070-ti-super|5090`; pool rig keys are
  `rtx-3090-24gb`-style, so `transfer_suggestions` (`transfer.rs`,
  `specs.contains_key(&run.gpu_model_id)`) never finds an anchor with the
  repo snapshot (`--gpu gpu-rtx-3080` → unknown as well).
  `GpuTransferSpec { id, arch_family, fp16_tflops: f64,
  memory_bandwidth_gib_s: f64, has_native_fp8 }`; factor =
  `effective_tflops(anchor)/effective_tflops(target)` (compute-bound,
  documented for diffusion). Tiers: `same_arch_family` 0.7,
  `roofline_transfer` 0.5, `source_class: derived`. `closest_rig_ids`
  (`lib.rs` line 271) is plain string similarity.

Device / vendor facts (sources in the QA doc §1–2):

- Galaxy S25 Ultra: SM-S938x; Snapdragon 8 Elite for Galaxy (SM8750-AC),
  Oryon 2× 4.47 GHz + 6× 3.53 GHz; Adreno 830; Hexagon NPU (no published
  TOPS); 12 GB LPDDR5X (16 GB on some 1 TB SKUs); released 2025-02-03.
- Snapdragon 8 Elite memory: dual-channel LPDDR5X up to 5.3 GHz
  (Qualcomm product brief) → 4×16-bit × 10.6 Gbps = **84.8 GB/s**
  theoretical. Snapdragon 888: 4×16-bit LPDDR5 @ 3200 MHz = **51.2 GB/s**
  (Qualcomm brief + AnandTech deep dive).
- Qualcomm AI Hub, `huggingface.co/qualcomm/Gemma-4-E2B-it` and
  `.../Gemma-4-E4B-it`, runtime `GENIEX_LLAMACPP`, precision `q4_0`,
  chipset **"Snapdragon® 8 Elite Mobile"**: E2B 512 ctx → 30.42 / 30.23 /
  26.66 tok/s; 4096 ctx → 22.98 / 19.18 / 20.62. E4B 512 ctx → 17.23 /
  16.78 / 16.02; 4096 ctx → 12.24 / 12.11 / 12.36. (Three rows per
  context = three device instances on the vendor's hosted farm.)
- Google LiteRT-LM Gemma 4 page: S26 Ultra (8 Elite **Gen 5**, next gen)
  E2B 47 CPU / 52 GPU tok/s, E4B 18 / 22. Different chip — never
  attached to the S25 Ultra row.
- `[A DEFINIR]`: usable app memory on Android out of 12 GB; sustained vs
  peak tok/s under thermal throttling; SM-S938B `navigator.userAgentData`
  `model` value as delivered by Samsung Internet vs Chrome.

## Dependencies and order

```text
S32a registry + formFactor (web data)   ──▶  S32b web-next picker/detect/llms.txt fix
S32c model catalog (HF-sourced)         ──▶  S32d vendor-claim import (needs S32e too)
S32e DB catalog: SoC rows + migration   ──▶  S32d
S32f Termux measured path (CLI)         independent; last (needs the owner's phone for the bar)
S32g canirunit bandwidth transfer       independent; small; first honest offline answer for a phone
```

Recommended dispatch order: g (one afternoon, closes the CLI half of the
incident) → a → b (user-visible with data already in the repo) → c → e →
d → f. None of these touch `benchmark_run` schema, signing, the
leaderboard query, or Vast.

---

## S32a — Mobile SoC registry + `formFactor` on derived rigs

Deliverables (exact paths):

- `apps/web/data/seed/mobile-socs.json` — the registry.
- `apps/web/scripts/enrich-mobile.mjs` — idempotent enrichment of the
  committed derived JSON.
- `apps/web/scripts/check.mjs` — new target `mobile` (added to
  `DELIVERED` and `TARGETS`).
- Regenerated `apps/web/data/derived/hardware.json` **and** its byte-copy
  `apps/web-next/public/data/derived/hardware.json` in the same commit.

Frozen contract:

```jsonc
// apps/web/data/seed/mobile-socs.json — one entry per SoC (not per phone)
[
  {
    "id": "snapdragon-8-elite",
    "vendor": "Qualcomm",
    "label": "Snapdragon 8 Elite",
    "formFactor": "phone",
    "match": ["snapdragon 8 elite", "sm8750", "sm-s93"],   // lowercase substrings, tested against rig key + label
    "bandwidthGBs": 84.8,
    "bandwidthSource": "https://docs.qualcomm.com/doc/87-83196-1/87-83196-1_REV_D_Snapdragon_8_Elite_Mobile_Platform_Product_Brief.pdf",
    "bandwidthNote": "dual-channel LPDDR5X up to 5.3 GHz; 4x16-bit x 10.6 Gbps",
    "deviceModels": { "SM-S938": "Galaxy S25 Ultra", "SM-S936": "Galaxy S25+", "SM-S931": "Galaxy S25" }
  },
  {
    "id": "snapdragon-888",
    "vendor": "Qualcomm",
    "label": "Snapdragon 888",
    "formFactor": "phone",
    "match": ["snapdragon 888"],
    "bandwidthGBs": 51.2,
    "bandwidthSource": "https://www.qualcomm.com/content/dam/qcomm-martech/dm-assets/documents/prod_brief_qcom_sd888_5g_1.pdf",
    "bandwidthNote": "4x16-bit LPDDR5 @ 3200 MHz",
    "deviceModels": {}
  },
  {
    "id": "tecno-pova-7-ultra",
    "vendor": "MediaTek",
    "label": "TECNO POVA 7 Ultra (Dimensity)",
    "formFactor": "phone",
    "match": ["tecno pova 7 ultra"],
    "bandwidthGBs": null,                                  // null beats a guess; fill only with a vendor URL
    "bandwidthSource": null,
    "bandwidthNote": "chipset/bandwidth not sourced at spec time — leave null or cite MediaTek",
    "deviceModels": {}
  }
]
```

Enrichment (`node scripts/enrich-mobile.mjs`, run from `apps/web/`):

- Reads `data/derived/hardware.json` and the registry; for every rig whose
  `key` or lowercased `label` contains any `match` substring, sets
  `formFactor: "phone"`, `soc: <registry id>`, and — only when the rig's
  `bandwidthGBs` is null — `bandwidthGBs` from the registry plus
  `bandwidthBasis: "vendor-spec"`. Every other rig gets
  `formFactor: "desktop"` (explicit, so consumers never branch on
  `undefined`). Existing keys, labels, `hwClass`, run counts: untouched.
- Idempotent: running twice yields a byte-identical file.
- After writing, copies the file to
  `../web-next/public/data/derived/hardware.json`.

`check.mjs mobile` must fail (exit 1) when: the registry file is missing
or any entry lacks `id|vendor|label|formFactor|match`; an entry has a
non-null `bandwidthGBs` with a null `bandwidthSource` (a number without a
source is an invented number); any rig in the derived file lacks
`formFactor`; the two derived `hardware.json` copies differ; or fewer
than 2 rigs carry `formFactor: "phone"` (the two known phones must match —
this pins the regex against silent regressions).

Mandatory behaviors (each with an assertion in `check.mjs mobile` or a
node test under `apps/web/tests/`):

1. `cpu-qualcomm-snapdragon-888-arm64` → `formFactor: phone`, `soc:
   snapdragon-888`, `bandwidthGBs: 51.2`, `bandwidthBasis: vendor-spec`.
2. `tecno-pova-7-ultra-5g-mali-g615-mc6-11-23gb` → `formFactor: phone`,
   `bandwidthGBs` stays `null` (no source ⇒ no number).
3. `rtx-3090-24gb` → `formFactor: desktop`, `bandwidthGBs: 936.2`
   unchanged (enrichment never overwrites an existing bandwidth).
4. Idempotency: second run → identical bytes.

Out of scope: touching `derive.mjs` identity rules or `hwClass`; adding
phones that have no rig in the pool (the S25 Ultra gets a *catalog* row
in S32e, not a fake rig here); any change to `pool.json`/`models.json`.

### Verificação

VERIFICACAO: test -f apps/web/data/seed/mobile-socs.json && grep -q '"mobile"' apps/web/scripts/check.mjs && grep -q '"formFactor"' apps/web/data/derived/hardware.json && cmp apps/web/data/derived/hardware.json apps/web-next/public/data/derived/hardware.json

### Barra

Two phone rigs matched, zero invented bandwidths, two copies identical.
Raise the "≥ 2 phones" floor when more phones enter the pool; never lower.

### Oráculo

- comando: `cd apps/web && node scripts/enrich-mobile.mjs && node scripts/check.mjs mobile && node scripts/check.mjs all`
- exit esperado: 0. Before implementation: exit 1 (unknown target
  `mobile` / missing script) — red by design.

---

## S32b — web-next: phones are selectable, detected, and the mobile pointer is honest

Depends on S32a (`formFactor` present in `hardware.json`).

Deliverables (exact paths):

- `apps/web-next/app/page.tsx` — rig options = top-24 by run count **plus
  every rig with `formFactor: "phone"`**, delivered to the client as two
  groups.
- `apps/web-next/app/home-client.tsx` — the `<select id="pick-rig">`
  renders `<optgroup label="Most tested">` and `<optgroup label="Phones &
  tablets">`; a `DeviceHint` banner above the verdict.
- `apps/web-next/lib/device.ts` — client-only detection helper.
- `apps/web-next/app/hardware/page.tsx` — a "Phones & tablets" section
  before the run-count grid, listing every phone rig regardless of run
  count; card text says `bandwidth vendor-spec` or `bandwidth unstated`
  according to `bandwidthBasis`.
- `apps/web-next/public/llms.txt`, `apps/web/site/llms.txt`, root
  `llms.txt` — mobile tour lines corrected (direction v3 D5 line).
- `apps/web-next/scripts/check-mobile.mjs` — the oracle script.

Frozen contract:

```ts
// apps/web-next/lib/device.ts — runs only in the browser, never in SSR
export type DeviceHint =
  | { kind: "none" }
  | { kind: "android-unknown" }                                  // UA says Android, no model hint granted
  | { kind: "known-phone"; model: string; label: string; socId: string; rigKey: string | null };
export async function detectDevice(registry: MobileSoc[], rigs: Rig[]): Promise<DeviceHint>;
// Order: navigator.userAgentData?.getHighEntropyValues(["model"]) → match
// model prefix against registry.deviceModels (e.g. "SM-S938B" → SM-S938);
// else /Android/i.test(navigator.userAgent) → android-unknown; else none.
// rigKey = the phone rig whose `soc` equals socId, if any; null otherwise.
// NEVER auto-selects. NEVER reads navigator.deviceMemory as a capacity
// (Chrome caps it at 8). WebGPU is not consulted (M3: vendor strings
// cannot name a phone).
```

Banner copy (frozen):

- known-phone with `rigKey`: `Looks like a <label> (<model>). Use it as the machine?` → button selects `rigKey`.
- known-phone without `rigKey`: `Looks like a <label> (<model>). The pool has no run on this phone yet — pick the closest phone or capture one.` → link `/submit`.
- android-unknown: `On a phone? Phone rigs are in the "Phones & tablets" group.`
- none: render nothing.

`llms.txt` fix (all three copies, same commit): replace
`m/index.html?as=human — mobile` with `/hardware — phones & tablets are
listed first on small screens` and `hardware.html?as=human` with
`/hardware`; the web-next copy must not name any path that returns 404 on
prod. The legacy `apps/web/site/llms.txt` may keep its own relative paths
(they resolve on the Pages mirror) but must add the line `Prod front:
https://www.bestmodel.run (Next.js); this mirror is a preview.`

Mandatory behaviors (asserted by `scripts/check-mobile.mjs` against a
production build served locally):

1. `GET /` HTML contains `<optgroup label="Phones` and both phone rig
   labels (`Qualcomm Snapdragon 888 ARM64`, `TECNO POVA 7 Ultra`).
2. `GET /hardware` HTML lists the phone labels **before** `CMP 170HX
   64GB` (string index order) and contains `bandwidth vendor-spec` for the
   Snapdragon 888 card.
3. `GET /llms.txt` contains no `m/index.html` and no `hardware.html`.
4. Every path named in `/llms.txt` under "Human tours" returns 200 from
   the local server.
5. `lib/device.ts` unit: `detectDevice` with a fake `navigator` exposing
   `userAgentData.getHighEntropyValues` resolving `{ model: "SM-S938B" }`
   returns `known-phone` with `socId: "snapdragon-8-elite"`, `label:
   "Galaxy S25 Ultra"`, `rigKey: null` (no S25 rig in the pool at spec
   time — the test must not fabricate one). With `userAgent`
   `...Android...` and no `userAgentData` → `android-unknown`. Desktop UA
   → `none`. Run with `node --test` (no new dependency).
6. Selecting the Snapdragon 888 rig, intent chat, 4-bit renders the one
   existing cell (`Gemma 4 E2B`, `6.2 tok/s`, badge `reported`, `n=1`) —
   this is the same join as today; the story must not alter `build()`.

Out of scope: any estimate for the S25 Ultra (no rig, no cell, no
number); PWA manifest (M13 — backlog); changes to `/wall`, `/submit`
(S32d/e own the picker), `/claims`; WEB-1 console single-source (D5
story) — but if WEB-1 has landed first, regenerate through its mechanism
rather than hand-copying.

### Verificação

VERIFICACAO: test -f apps/web-next/lib/device.ts && grep -q 'Phones & tablets' apps/web-next/app/home-client.tsx && ! grep -q 'm/index.html' apps/web-next/public/llms.txt

### Barra

Zero 404s reachable from `/llms.txt`; phone rigs visible from the first
screen on `/` and `/hardware`; detection suggests, never decides.

### Oráculo

- comando: `cd apps/web-next && npm ci && npm run build && node --test lib/*.test.mjs && node scripts/check-mobile.mjs`
  (the check script starts `next start -p 3999`, fetches `/`, `/hardware`,
  `/llms.txt` and every human-tour path, asserts 1–4, and kills the server;
  it exits non-zero on any assertion or if the port is busy — never skips).
- exit esperado: 0. Before implementation: exit 1 (script missing) — red
  by design.

---

## S32c — Model catalog: the mobile SOTAs, HF-sourced

Deliverables: rows appended to `infra/seed/model_releases.json` **only
through** `infra/scripts/expand_catalog_from_hf.py` (S22 mechanism), plus
the script's run log pasted into the commit message body.

Candidate HF ids (the script decides — a 404 or a `config.json` without
the needed fields drops the row; nothing is typed by hand):

```text
google/gemma-4-E2B-it        google/gemma-4-E4B-it        google/gemma-3n-E4B-it
Qwen/Qwen3.5-2B              Qwen/Qwen3.5-0.8B (exists: model-qwen3-5-0-8b — skip)
LiquidAI/LFM2.5-1.2B-Instruct  LiquidAI/LFM2.5-2.6B       LiquidAI/LFM2.5-8B-A1B
mistralai/Ministral-3-3B-Instruct-2512
microsoft/Phi-4-mini-instruct
nvidia/NVIDIA-Nemotron-3-Nano-4B
openbmb/MiniCPM5-1B          openbmb/MiniCPM5-2B
ibm-granite/granite-4.0-h-micro
```

Rules: ids follow the existing `model-<family>-<size>` convention and
`family` values follow the existing list (add `gemma-4`, `gemma-3n`,
`lfm2.5`, `ministral-3`, `phi-4`, `nemotron-3`, `minicpm5`, `granite-4`
only if the script emits them from the card); MoE rows must carry
`active_parameter_count_billion` and `expert_count`/`experts_per_token`
from config; Gemma E-series rows record the **effective** count the card
states (E2B/E4B) in `release_name` and the config's true count in
`parameter_count_billion` — never the other way round. Gated models
(Gemma, Llama) need `HF_TOKEN`; without it the script must say so and
skip, not invent.

Mandatory behaviors: `uv run pytest packages/domain-schema -q` stays green
(rows validate as `ModelRelease`); `infra/seed/load_seed.py` idempotency
(second run inserts 0); `import_localmaxxing.py --dry-run` against a
local stack reports **fewer** `nomodel` cells than before this story
(the pool already has runs for these models — the count is measured at
execution and written into the commit message; the spec does not guess
it).

Out of scope: quantization profiles (the GGUF q4_0/Q4_K_M ids already
exist), runtimes (M11 → S26), any model > 12 B.

### Verificação

VERIFICACAO: python3 -c "import json;m=json.load(open('infra/seed/model_releases.json'));ids={x['id'] for x in m};assert any('gemma-4' in i for i in ids) and any('qwen3-5-2b' in i for i in ids), ids"

### Barra

Every new row traceable to an HF `config.json` fetch in the script log;
zero hand-typed parameter counts.

### Oráculo

- comando: `uv run python infra/scripts/expand_catalog_from_hf.py --help >/dev/null && uv run pytest packages/domain-schema -q && make seed`
  (`make seed` needs `make infra-up`; the executor runs it against the
  local compose stack, ports per root `AGENTS.md` golden rule 1).
- exit esperado: 0 and `loaded N rows into model_release` with N ≥ 77 +
  number of rows the script actually emitted. Before implementation the
  VERIFICACAO one-liner fails (no gemma-4 id) — red by design.

---

## S32e — DB catalog: mobile SoC rows in `gpu_model` (migration 0018)

Listed before S32d because S32d depends on it.

Deliverables (exact paths):

- `infra/migrations/0018_mobile_soc.sql` — append-only:

```sql
BEGIN;
ALTER TABLE gpu_model ALTER COLUMN tdp_watt DROP NOT NULL;   -- phones publish no TDP; NULL is the honest value
ALTER TABLE gpu_model
  ADD COLUMN form_factor TEXT NOT NULL DEFAULT 'desktop'
    CHECK (form_factor IN ('desktop', 'laptop', 'phone', 'tablet', 'sbc')),
  ADD COLUMN device_models TEXT[] NOT NULL DEFAULT '{}';       -- e.g. {SM-S938B,SM-S938U}
COMMIT;
```

- `packages/domain-schema/src/gpu_spec.py`: `tdp_watt: int | None =
  Field(default=None, gt=0)`; `form_factor: Literal['desktop','laptop',
  'phone','tablet','sbc'] = 'desktop'`; `device_models: list[str] = []`.
  Existing tests that assert `tdp_watt` rejects 0/negative stay; add a
  test that `None` is accepted.
- `infra/seed/gpu_models.json` — two rows (values below are the only
  ones permitted; anything not listed is `null`):

```jsonc
{
  "id": "gpu-snapdragon-8-elite-galaxy-12gb",
  "vendor": "Qualcomm",
  "marketing_name": "Snapdragon 8 Elite for Galaxy (Galaxy S25 Ultra, 12 GB)",
  "vram_mib": 12288,                 // shared LPDDR5X; usable-by-app fraction is [A DEFINIR] (S32f measures it)
  "memory_bandwidth_gib_s": 84.8,    // seed convention: vendor GB/s figure (see RTX 4090 = 1008.0)
  "fp16_tflops": null, "int8_tops": null, "tdp_watt": null,
  "pcie_generation": null, "pcie_lane_width": null, "supports_nvlink": false,
  "released_at": "2025-02-03",
  "form_factor": "phone",
  "device_models": ["SM-S938B", "SM-S938U", "SM-S938N", "SM-S9380", "SM-S938W"]
},
{
  "id": "gpu-snapdragon-888-12gb",
  "vendor": "Qualcomm",
  "marketing_name": "Snapdragon 888 (12 GB)",
  "vram_mib": 12288, "memory_bandwidth_gib_s": 51.2,
  "fp16_tflops": null, "int8_tops": null, "tdp_watt": null,
  "pcie_generation": null, "pcie_lane_width": null, "supports_nvlink": false,
  "released_at": "2020-12-01",
  "form_factor": "phone",
  "device_models": []
}
```

- `infra/seed/load_seed.py` — `columns` for `gpu_model` gain
  `form_factor`, `device_models`.
- Lockstep (domain-schema `AGENTS.md` change checklist): every
  `PostgresSession` SELECT that materialises a `gpu_model` row and the
  FakeDatabase row shape expose the two new keys; `tests/test_session_contract.py`
  and `tests/test_fake_leaderboard_derivation.py` stay green; add
  `tests/test_mobile_catalog.py` (2 backends, Postgres leg skips **only**
  on `psycopg.OperationalError`).
- `apps/public-api/src/routes/catalog_route.py` — two additive routes
  next to the existing `/v1/model-releases` and
  `/v1/quantization-profiles`: `GET /v1/gpu-models` (id, vendor,
  marketing_name, vram_mib, memory_bandwidth_gib_s, form_factor,
  device_models) and `GET /v1/inference-runtimes` (id, engine, version).
  Same response shape conventions as their siblings; Fake + Postgres.
- `apps/web-next/app/submit/submit-client.tsx` — the Hardware field
  becomes a `<datalist>`/select fed from `GET /v1/gpu-models`, with
  phones grouped first when `detectDevice()` (S32b) says `known-phone`;
  free text remains allowed for unknown hardware. The form also sends
  `inference_runtime_id` from a select fed by `GET /v1/inference-runtimes`
  (5 ids today; M11 notes the mobile ids arrive with S26).
- `apps/public-api/src/services/import_localmaxxing_claims.py`
  `match_gpu`: extend the alias source so `cpu-qualcomm-snapdragon-888-arm64`
  resolves to `gpu-snapdragon-888-12gb` (suffix match on
  `marketing_name` already exists; add `device_models` and the
  `snapdragon 888` token as aliases). Measured effect recorded in the
  commit: `--dry-run` shows the Gemma 4 E2B / Snapdragon 888 cell mapped
  to a gpu id (it is `null` today).

Mandatory behaviors (tests):

1. `GpuSpec` accepts the two rows verbatim; rejects `form_factor: "car"`.
2. Fake + Postgres: `fetch_gpus_by_ids(["gpu-snapdragon-8-elite-galaxy-12gb"])`
   returns the row with `form_factor == "phone"`, `tdp_watt is None`.
3. `compute_claim_prior` for `model-llama-3-2-3b` / `q-gguf-q4-k-m` /
   this gpu id returns a roofline prior (bandwidth 84.8 drives it) and
   the response carries the existing `formula` labelling — the caveat
   text `shared 12 GB; Android keeps part of it` is attached in
   `roofline.note` for `form_factor == "phone"` rows only.
4. Existing 29 rows unchanged (`git diff` on those objects is empty).
5. `make migrate` twice is idempotent; `make gate` green.

Out of scope: `cpu_model` rows for the Oryon CPU; NPU TOPS (unpublished);
any `benchmark_run` shape change; leaderboard rendering of phones (they
render whenever a validated run exists — no special case).

### Verificação

VERIFICACAO: test -f infra/migrations/0018_mobile_soc.sql && grep -q '"gpu-snapdragon-8-elite-galaxy-12gb"' infra/seed/gpu_models.json && grep -q 'form_factor' packages/domain-schema/src/gpu_spec.py

### Barra

Zero invented numbers: every non-null figure in the two rows is one of
the values listed above; NULL is the answer for the rest.

### Oráculo

- comando: `make infra-up && make seed && uv run pytest tests/test_mobile_catalog.py packages/domain-schema -q && uv run pytest tests/test_session_contract.py -q`
- exit esperado: 0 on both backends (DATABASE_URL set). Before
  implementation: exit 5 (test file not collected) — red by design.

---

## S32d — Vendor numbers as claims: Qualcomm AI Hub import

Depends on S32c (Gemma 4 E2B/E4B ids) and S32e (`gpu-snapdragon-8-elite-galaxy-12gb`).

Deliverables:

- `infra/scripts/import_qai_hub.py` — same shape as
  `import_localmaxxing.py` (`--dry-run` / `--apply` / `--source-url` /
  `--snapshot-at` / `--limit`), reading a **checked-in snapshot**
  `infra/data/qai-hub/<YYYY-MM-DD>/<model>.json` that the executor
  captures from the HF card's Performance Summary table (fields:
  `model_hf_id`, `runtime`, `precision`, `chipset`, `context_length`,
  `response_rate_tok_s`, `ttft_range_s`, `source_url`, `captured_at`).
  The snapshot is data with provenance; hand-editing a number in it is
  fraud of source (same rule as `export-contributors.py`).
- `apps/public-api/src/services/import_qai_hub_claims.py` — builds
  `run_claim` rows: `source = 'qai-hub'`, `claimant_id = NULL`,
  `external_ref = f"qai-hub:{model_hf_id}:{chipset}:{context_length}:{row_index}"`,
  `provenance = {source_url, snapshot_at, importer: "import_qai_hub", chipset, runtime, precision}`,
  `gpu_model_id` = the S32e row **only when** `chipset ==
  "Snapdragon® 8 Elite Mobile"` (retail 8 Elite; the "for Galaxy" part
  is the same die — record `provenance.chip_variant_note = "retail 8
  Elite; S25 Ultra runs the ~3% higher-clocked for-Galaxy bin"`);
  rows for `8 Elite Gen 5`, `X Elite`, `X2 Elite`, Dragonwing are imported
  with `gpu_model_id = NULL` until their catalog rows exist (never bound
  to the S25 row). `quantization_profile_id = 'q-gguf-q4-k-m'` is **not**
  assumed: q4_0 ≠ Q4_K_M — leave null and put `precision: q4_0` in
  provenance. `inference_runtime_id = 'llama-cpp'` (GenieX is a llama.cpp
  fork; note it in provenance). `context_tokens = context_length`.
  `claimed_metrics = {decode_tok_s: response_rate_tok_s, ttft_ms_min,
  ttft_ms_max}` — the metric keys must exist in `METRIC_UNITS`
  (`submit_benchmark_run.py`); if `ttft_ms_min/max` do not, keep only
  `decode_tok_s` and put the TTFT range in `note`.
- Idempotent per `external_ref`; `--dry-run` prints `total / existing /
  imported / unbound_gpu / nomodel`.

Snapshot scope: only the **phone chipset rows** of each card —
"Snapdragon® 8 Elite Mobile" and "Snapdragon® 8 Elite Gen 5 Mobile" (3
device instances × 2 context lengths = 6 rows each, 12 per card). X
Elite / X2 Elite / Dragonwing rows are laptop and IoT parts: out of scope
for a phone story, not captured.

Mandatory behaviors (tests, Fake + Postgres): 24 rows from the two Gemma
cards import on first `--apply`, 0 on the second; the twelve "Snapdragon®
8 Elite Mobile" rows carry the S25 gpu id and a frozen prior with a
roofline leg; the twelve Gen 5 rows carry `gpu_model_id NULL` and a prior
without roofline; every row has `provenance.source_url` starting with
`https://huggingface.co/qualcomm/`; none appears in `/v1/leaderboard`
(claims never do — assert against the Fake leaderboard derivation).

Prod procedure (owner, after review): `--dry-run` against prod → paste
counts into `docs/transparency.md` under a new "qai-hub vendor claims"
line → `--apply`. Web: the claims wall (`/claims`) shows them immediately
with `source = qai-hub`; the home's claims tier surfaces them as "other
rigs" claims. The S25 Ultra remains a **catalog** row, not a pool rig —
it becomes a selectable machine on `/` only when a real run lands (S32f).

Out of scope: LiteRT-LM (Google) numbers — different chip (S26 Ultra)
and no per-device table to snapshot yet; Liquid's "~30 tok/s on a
smartphone" (device unspecified → not importable); anything that writes
to `benchmark_run`.

### Verificação

VERIFICACAO: test -f infra/scripts/import_qai_hub.py && ls infra/data/qai-hub/*/Gemma-4-E2B-it.json >/dev/null && grep -q "qai-hub" apps/public-api/src/services/import_qai_hub_claims.py

### Barra

`--apply` twice ⇒ second run imports 0. Zero rows bound to the S25 gpu id
whose provenance chipset is not exactly "Snapdragon® 8 Elite Mobile".

### Oráculo

- comando: `uv run pytest tests/test_import_qai_hub.py -q && uv run python infra/scripts/import_qai_hub.py --dry-run`
- exit esperado: 0 on both backends; dry-run prints five counters.
  Before implementation: exit 5 — red by design.

---

## S32f — Termux measured path: `benchmark-probe` on Android

Independent of a–e for code; the **bar** needs the owner's phone.

Deliverables:

- `cli/benchmark-probe/src/collect_system_topology.rs`: an
  `else if cfg!(target_os = "android")` branch in each detector, calling
  pure parsers in a new module `cli/benchmark-probe/src/android_topology.rs`:

```rust
// android_topology.rs — pure, unit-tested on Linux CI with string fixtures
pub fn parse_getprop_os_version(release: &str, one_ui: Option<&str>) -> String;  // "16" + " · One UI 8" when ro.build.version.oneui present
pub fn parse_getprop_cpu_model(soc_model: &str, product_model: &str, board_platform: &str) -> String; // "SM8750 (sun) · SM-S938B" — frozen shape: "<ro.soc.model> (<ro.board.platform>) · <ro.product.model>"
pub fn parse_egl_gpu(egl: &str, meminfo_total_kib: Option<u64>) -> Vec<GpuInfo>; // name from ro.hardware.egl ("adreno") → "Adreno (ro.hardware.egl=adreno)"; vram_mib None — shared memory is NOT VRAM
pub fn parse_meminfo_total_kib(meminfo: &str) -> Option<u64>;
```

  Runtime calls: `getprop ro.build.version.release`,
  `ro.build.version.oneui`, `ro.soc.model`, `ro.product.model`,
  `ro.board.platform`, `ro.hardware.egl`; `/proc/meminfo`. Missing
  `getprop` → empty strings, never a panic (Termux without `su` can read
  all of these).
- `docs/agent-quickstart.md` § "Android (Termux)": `pkg install rust
  clang make git openssl perl` → `cargo build --release -p benchmark-probe`
  (native build; **no NDK cross-compile is required or specified**) →
  `llama-cli` on `PATH` (Termux `pkg install llama-cpp`, or build
  llama.cpp from source) → `benchmark-probe --runtime llama.cpp --model
  <path.gguf> --prompt-tokens ... --generated-tokens ...` — the probe
  already drives `llama-cli` directly
  (`detect_runtime_installations.rs` → `detect_install("llama-cli")`,
  `execute_benchmark_scenario.rs` → `run_llama_cpp_scenario`) and parses
  its stdout; no server, no new flag in this story. Note the known
  blockers honestly: `openssl-sys` vendored needs `perl`; Termux's
  `$PREFIX` paths; thermal throttling — run on a cool phone, plugged in,
  and say so in the report notes.
- `cli/benchmark-probe/tests/android_topology_test.rs` — fixtures for
  an SM-S938B (`ro.soc.model=SM8750`, `ro.board.platform=sun`,
  `ro.product.model=SM-S938B`, `ro.hardware.egl=adreno`, meminfo
  `MemTotal: 11xxxxxx kB` — use a placeholder value and assert the
  parser, not the phone) and for a missing-getprop machine.
- Report side: the topology lands in the existing `system_topology`
  artifact; `hardware_fingerprint` uses the frozen cpu_model shape above
  so two runs from the same phone model collide as intended. The worker
  path for an unresolved GPU already exists (`UNBOUND_HARDWARE`); this
  story adds a test that a report whose topology names `SM-S938B` and
  whose submission carries `gpu_model_id =
  "gpu-snapdragon-8-elite-galaxy-12gb"` (S32e) passes the roofline leg
  with `peak_vram_mib` read as **peak RSS** (the metric kind
  `peak_ram_mib` is reserved in `MetricKind` — use it if the probe can
  report RSS; otherwise leave the VRAM leg `n/a` for phones and say so in
  evidence, never fake a VRAM number).

Mandatory behaviors: parsers tested on Linux CI; `cargo build` on Linux
unaffected; a Linux run of the binary prints the same topology as before
(no regression in `tests/*smoke*`); documentation section present.

Bar (owner, not CI): one signed report from an SM-S938x reaches
`status=validated` in prod and renders on `/wall` with badge
`measured_signed`. The measured `peak_ram_mib` becomes the first value
for the `[A DEFINIR]` "usable memory" in S32e's caveat — recorded in
`docs/findings.md` as F9, never typed from memory.

Out of scope: an Android app; iOS; MLC/LiteRT-LM probes (runtime ids
arrive with S26); GPU offload flags for Adreno (`GGML_OPENCL`) — a
follow-up once a CPU-only baseline exists.

### Verificação

VERIFICACAO: grep -q 'target_os = "android"' cli/benchmark-probe/src/collect_system_topology.rs && test -f cli/benchmark-probe/src/android_topology.rs && grep -q "Termux" docs/agent-quickstart.md

### Barra

Parsers frozen by fixtures; zero VRAM numbers for shared memory; the
first validated phone run is the bar, and it is the owner's.

### Oráculo

- comando: `cargo test -p benchmark-probe --quiet && cargo run -p benchmark-probe --quiet -- --runtime mock --model qwen3:8b`
- exit esperado: 0 with the new android tests counted in the suite.
  Before implementation: `cargo test` fails to compile the missing
  test target — red by design.

---

## S32g — canirunit: bandwidth transfer for decode, rig-keyed specs, phone rows, unknown-query ledger

Independent of a–f. Closes the CLI half of the incident (W3, W8).

Deliverables (exact paths):

- `cli/canirunit/gpu_transfer_specs.json` — entries gain
  `"aliases": [<pool rig keys>]` (e.g. `gpu-rtx-3090` → `["rtx-3090-24gb"]`,
  `gpu-rtx-4090` → `["rtx-4090-24gb"]`, and so on for the 5 existing
  rows, taken from `canirunit rigs` output, never guessed) and two phone
  rows:

```jsonc
{ "id": "cpu-qualcomm-snapdragon-888-arm64", "arch_family": "adreno-6xx",
  "fp16_tflops": null, "memory_bandwidth_gib_s": 51.2, "has_native_fp8": false,
  "source": "Qualcomm SD888 product brief: 4x16-bit LPDDR5 @ 3200 MHz" },
{ "id": "snapdragon-8-elite-12gb", "arch_family": "adreno-8xx",
  "fp16_tflops": null, "memory_bandwidth_gib_s": 84.8, "has_native_fp8": false,
  "source": "Qualcomm 8 Elite product brief: dual-channel LPDDR5X up to 5.3 GHz" }
```

- `cli/canirunit/src/transfer.rs`:
  `fp16_tflops: Option<f64>`; loader indexes every spec by `id` **and**
  each alias; **metric-aware factor**: for `decode_tok_s` (bandwidth-bound)
  `rate_factor = bw(target) / bw(anchor)`; for `seconds_per_clip` /
  `frames_per_s` keep the effective-TFLOPS algebra and skip anchor pairs
  where either side has `fp16_tflops: null` (never substitute a number).
  Explanation string names the anchor, the metric regime
  (`bandwidth-bound` / `compute-bound`) and the numeric factor.
- `cli/canirunit/src/lib.rs` `closest_rig_ids`: strip the trailing
  `-<n>gb[-x<k>]` suffix from both sides before scoring, so a shared
  memory size alone never makes a "closest" rig.
- `cli/canirunit/src/main.rs`: on `match_class: unknown`, if
  `BESTMODEL_QUERY_LOG` is set, append one JSON line
  `{"ts": <RFC3339>, "event": "unknown_hardware_query", "gpu": <id>, "task": <metric>, "corpus": <path>}`
  to that file; unset → nothing is written (tests stay hermetic). Exit
  code stays 3.
- `docs/agent-quickstart.md`: the suggest example gains the phone case
  and the one-line explanation of `derived` transfers.

Mandatory behaviors (tests in `cli/canirunit/tests/`):

1. Pinned arithmetic: `suggest --gpu snapdragon-8-elite-12gb --task
   decode_tok_s --runs apps/web/data/derived/pool.json --gpus
   cli/canirunit/gpu_transfer_specs.json` → exit 0, `match_class:
   roofline_transfer` (families differ), one suggestion for
   `google-gemma-4-e2b-it` with `expected = 6.2 × 84.8 / 51.2 = 10.27`
   (±0.01), `source_class: derived`, `n_runs: 1`, explanation containing
   `bandwidth-bound` and `1.656`. **This number is an estimate of an
   estimate** (1 harvested run × vendor bandwidth ratio) and the
   confidence tier must say so (0.5 tier, unchanged).
2. Aliases: `suggest --gpu rtx-3080-12gb --task decode_tok_s ... --gpus
   specs` still returns `exact_gpu` (aliases never override a real
   match); `suggest --gpu gpu-rtx-4090 ...` resolves through the alias
   to the `rtx-4090-24gb` runs.
3. Video metrics with a `null`-TFLOPS target produce **no** transferred
   suggestion (unknown + hint), never a bandwidth-scaled video number.
4. `closest_rig_ids("snapdragon-8-elite-12gb")` puts
   `cpu-qualcomm-snapdragon-888-arm64` first and contains no
   `arc-b580-12gb`.
5. Ledger: with `BESTMODEL_QUERY_LOG=$TMP/q.jsonl`, an unknown query
   appends exactly one valid JSON line; without the variable no file is
   created. `confidence_property_test.rs` and existing suites untouched
   and green.

Out of scope: any change to the pool snapshot; new metrics; uploading
the ledger anywhere (it is local demand evidence for the owner, read by
hand).

### Verificação

VERIFICACAO: grep -q '"aliases"' cli/canirunit/gpu_transfer_specs.json && grep -q 'snapdragon-8-elite-12gb' cli/canirunit/gpu_transfer_specs.json && grep -q 'bandwidth-bound' cli/canirunit/src/transfer.rs && grep -q 'BESTMODEL_QUERY_LOG' cli/canirunit/src/main.rs

### Barra

The phone answer is `derived` with factor 1.656 from exactly one anchor;
zero invented TFLOPS; the five desktop rows keep their numbers.

### Oráculo

- comando: `cargo test -p canirunit --quiet && cargo run -q -p canirunit -- suggest --gpu snapdragon-8-elite-12gb --task decode_tok_s --runs apps/web/data/derived/pool.json --gpus cli/canirunit/gpu_transfer_specs.json`
- exit esperado: 0 with `"match_class": "roofline_transfer"` on stdout.
  Before implementation: exit 3 (`unknown`) — red by design (reproduced
  2026-09-20).

---

## Registration (same commit as the first landed story)

- `specs/en/AGENTS.md`: row `S32-mobile-soc-support | PLANNED | stories a–f`.
- `docs/POINTERS.md`: job card `mobile-s32` (OPEN: this spec, the QA doc,
  nearest `AGENTS.md`; SKIP: everything else).
- `docs/backlog.md`: one line under Cross-track notes linking S32; M13
  (PWA manifest) and M11 (mobile runtime ids → S26) as backlog lines.
- `llms.txt` (root) "Specs index" line mentions S32 once S32b lands
  (the agent surface must not advertise a spec before the 404 it fixes
  is fixed).
