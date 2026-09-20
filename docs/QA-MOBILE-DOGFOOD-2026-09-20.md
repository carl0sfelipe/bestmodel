# QA dogfood — bestmodel.run from a Galaxy S25 Ultra (2026-09-20)

> Owner request: "I bought an S25 Ultra — what can it run, how would I use
> bestmodel.run on it, and how do we get the mobile SOTAs on the site?"
> This is the read-side record: device facts (sourced), what the phone
> ecosystem runs today (vendor numbers, **not** pool data), and what the
> live site does when that phone opens it. The write-side answer is the
> executable spec `specs/en/S32-mobile-soc-support.md`.
>
> Rule of this document: every number carries its source. Nothing here is
> a pool measurement unless it says `pool`. Vendor figures are labelled
> `vendor-reported` — they are orientation, never a bestmodel cell.

## 1. The device (sourced)

| Field | Value | Source |
|---|---|---|
| Model | Samsung Galaxy S25 Ultra (SM-S938x), released 2025-02-03 | GSMArena spec sheet |
| SoC | Qualcomm SM8750-AC **Snapdragon 8 Elite for Galaxy**, TSMC 3 nm; Oryon V2 CPU 2× 4.47 GHz + 6× 3.53 GHz (overclocked vs the 4.32 GHz retail 8 Elite) | GSMArena; Android Authority (Qualcomm confirmation) |
| GPU | Adreno 830 (sliced architecture, OpenCL / Vulkan) | GSMArena; Qualcomm product brief |
| NPU | Hexagon NPU, 8 scalar + 6 vector accelerators, INT4/INT8/INT16/FP16; Samsung: "40 % faster AI" vs 8 Gen 3 for Galaxy; Qualcomm publishes **no TOPS figure** for this part | Qualcomm 8 Elite product brief; samsung.com |
| Memory | 12 GB LPDDR5X (16 GB only on some 1 TB regional SKUs); SoC supports dual-channel LPDDR5X up to 5.3 GHz → 4×16-bit × 10.6 Gbps = **84.8 GB/s theoretical** | GSMArena (capacities); Qualcomm brief (5.3 GHz, dual-channel); bandwidth derivation as in Android Authority |
| Storage | 256 GB / 512 GB / 1 TB UFS 4.0, no card slot | GSMArena |
| OS | Android 15 at launch, 7 major upgrades promised; One UI 8 available | GSMArena |
| Battery / thermals | 5000 mAh, 45 W wired; larger vapor chamber than S24 Ultra | samsung.com |

What this means for local inference, in the site's own vocabulary: the
phone is a **UNIFIED**-memory machine with 12 GB shared between OS, apps
and model, ~85 GB/s of bandwidth at best (a 3090 has 936 GB/s; an M4 has
120 GB/s), and a hard thermal ceiling. Decode speed is bandwidth-bound, so
4-bit models of 1–4 B parameters are the sweet spot; 8–9 B at Q4 fits on
paper (≈5–6 GB) but leaves little for Android and throttles quickly. No
pool measurement exists yet for how much of the 12 GB an app can actually
hold — that number is `[A DEFINIR]` until the Termux probe (S32f) measures
it.

## 2. What runs on it today (vendor-reported, not pool)

Numbers below are published by the vendors on the **retail Snapdragon 8
Elite** (same die, ~3 % lower prime clock than the "for Galaxy" part) or on
the **next-generation** S26 Ultra where marked. They are what a bestmodel
cell would be *compared against*, not what the site may display as this
phone's number.

| Model (4-bit) | Weights on disk | Decode tok/s | Where measured | Source |
|---|---|---|---|---|
| Gemma 4 E2B-it, q4_0 | ≈2.8 GB (+0.2 GB vision projector) | **26.7–30.4** @ 512 ctx · 19.2–23.0 @ 4096 ctx | Snapdragon 8 Elite Mobile, GenieX llama.cpp | huggingface.co/qualcomm/Gemma-4-E2B-it (Performance Summary) |
| Gemma 4 E4B-it, q4_0 | ≈5.3 GB (+1.0 GB projector) | **16.0–17.2** @ 512 ctx · 12.1–12.4 @ 4096 ctx | Snapdragon 8 Elite Mobile, GenieX llama.cpp | huggingface.co/qualcomm/Gemma-4-E4B-it |
| Gemma 4 E2B (LiteRT-LM) | — | 47 CPU / 52 GPU | **S26 Ultra** (8 Elite Gen 5 — next gen, upper bound) | ai.google.dev/edge/litert-lm/models/gemma-4 |
| Gemma 4 E4B (LiteRT-LM) | — | 18 CPU / 22 GPU | **S26 Ultra** (next gen) | same |
| LFM2.5-2.6B | < 2.5 GB RAM incl. 128 K ctx (vendor) | "~30 on a smartphone" (device unspecified) | vendor figure | Liquid AI launch coverage |
| Qwen3.5 4B, Q4_K_M | ≈2.7 GB (+0.4 GB projector) | no phone figure published | — | Luxand on-device table (sizes only) |
| Qwen3.5 2B, Q4_K_M | ≈1.3 GB | no phone figure published | — | same |
| LFM2.5-8B-A1B, Q4_K_M | ≈5.2 GB (1.5 B active) | no phone figure published | — | same |
| Gemma 4 26B-A4B, UD-Q2_K_XL | ≈10.5 GB | does not fit a 12 GB phone with Android resident | — | same (size only) |

Reading: on this phone, **Gemma 4 E2B and Qwen3.5 2B/4B are the
"instant" tier (≥ 25 tok/s plausible), Gemma 4 E4B / LFM2.5-2.6B /
Ministral 3 3B / Nemotron 3 Nano 4B the "comfortable" tier (12–20 tok/s),
and anything ≥ 8 B dense is a curiosity** (fits, slow, hot). Vision and
audio input are on-device with the Gemma 4 E-series. None of this is a
bestmodel number until someone measures it on an SM-S938x.

### Runtimes on Android (what a user actually installs)

| Runtime / app | Engine | Formats | Notes |
|---|---|---|---|
| Google AI Edge Gallery | LiteRT-LM (LLM Inference API) | `.litertlm` / `.task` from the LiteRT community on HF | Play Store app; built-in **Benchmark** (TTFT, decode tok/s, peak memory) — the only phone app that already emits the metrics our claim form asks for; Gemma-centric catalog |
| PocketPal AI | llama.cpp (CPU, NEON) | any GGUF from HF | Broadest model choice; shows tok/s per reply |
| MLC Chat | MLC-LLM (Vulkan/OpenCL on Adreno) | pre-compiled MLC bundles (~15–20 models) | Fastest GPU path on Snapdragon flagships; small catalog |
| Termux + llama.cpp | llama.cpp (`llama-server`, `llama-bench`) | GGUF | The only path that can run **our Rust probe** and produce a **signed** report (S32f) |
| Qualcomm GenieX / AI Hub | llama.cpp fork + QNN (Hexagon NPU) | Qualcomm-exported bundles | Where the vendor numbers above come from; Snapdragon-only |
| ExecuTorch | PyTorch mobile runtime (CPU/Vulkan/QNN delegate) | `.pte` | Developer-facing, not an end-user app |

## 3. Dogfood: opening bestmodel.run on the phone

Method: live prod (`www.bestmodel.run`, Vercel = `apps/web-next`) fetched
with the S25 Ultra Chrome user agent (`SM-S938B`, Android 16) via curl,
and browsed in Chrome device emulation "Galaxy S25 Ultra" 412×915 CSS px,
DPR 3, same UA (session 2026-09-20 ~16:00 UTC; screenshots
`qa_s25_*.png` attached to PR #12); the legacy GitHub Pages mirror checked
where prod points to it; repo sources read at `main` `16cf014`. Each
finding names the file that produces it and says whether it was seen
live or read from code.

What the phone user sees first (live): the home loads with the machine
select pre-set to `CMP 170HX 64GB · 1819 runs` (a mining GPU) and the
verdict `255.9 tok/s · Qwen3.8-27B-W6A16-AutoRound · measured · n=11 ·
4-bit on CMP 170HX 64GB`. Nothing on the screen tells a phone owner
that this number is not theirs until they open the select and find no
phone in it.

| # | Finding | Evidence | Severity |
|---|---|---|---|
| M1 | **The phone cannot be picked on the home.** The "02 the machine" select offers the top **24** rigs by run count; the only phone-class rigs in the pool have 1 and 4 runs and never make the cut. Live: `#pick-rig` has exactly 24 options, zero matches for Snapdragon/Galaxy/Pixel/Tensor/iPhone/Dimensity/TECNO/Mali. A phone user gets a desktop GPU pre-selected and the claims-tier fallback of *other* rigs. | `apps/web-next/app/page.tsx` `RIG_LIMIT = 24`; live console; `qa_s25_home_hero.png` | blocker for the mobile journey |
| M2 | **No Snapdragon 8 Elite / Galaxy S25 rig exists anywhere.** Phone-class rigs in the pool: `cpu-qualcomm-snapdragon-888-arm64` (12 GB, class CPU_ONLY, 1 run: Gemma 4 E2B 6.2 tok/s reported, llama.cpp) and `tecno-pova-7-ultra-5g-mali-g615-mc6-11-23gb` (11.23 GB, class UNIFIED, 4 runs). Same kind of device, two different classes, both with `bandwidthGBs: null`. | `apps/web-next/public/data/derived/{hardware,pool}.json` | data gap |
| M3 | **No device detection on prod.** web-next has no client-side hardware hint at all. The legacy tour's WebGPU probe maps vendor strings for nvidia/amd/intel/apple only; a Qualcomm Adreno adapter falls through to the toast "No WebGPU detection here — pick a reference rig". | `apps/web/site/assets/mobile-page.mjs` `guessRigByVendor` | UX gap |
| M4 | **The agent surface advertises a mobile tour that 404s on prod.** `www.bestmodel.run/llms.txt` lists `m/index.html?as=human — mobile` and `hardware.html?as=human`; on web-next `/m/[slug]` is the *model* page, so `/m/index.html` → 404 and `/hardware.html` → 404. The tour only exists on the Pages mirror, which direction v3 D5 declares "preview, never prod". | `apps/web-next/public/llms.txt` lines 8–10, 60–61; curl 404 | D5 line (copy bug) |
| M5 | **Phones are misfiled by class.** The derive step keys rigs by `hwClass` from the upstream pool (DISCRETE_GPU / UNIFIED / CPU_ONLY) and has no notion of form factor; `seedBandwidth` returns `null` for CPU_ONLY and the bandwidth seed has no SoC names, so no extrapolation is ever possible for a phone. | `apps/web/scripts/derive.mjs` `rigIdentity`, `seedBandwidth`; `apps/web/data/seed/bandwidth.json` | pipeline gap |
| M6 | **`/hardware` buries phones.** Cards are ordered by run count only; live HTML: 185 cards, TECNO POVA at 101, Snapdragon 888 at 140 (`1 runs · 12 GB · CPU_ONLY · 1 GPU · bandwidth unstated`). | `apps/web-next/app/hardware/page.tsx`; live `/hardware` HTML | UX gap |
| M7 | **The DB catalog has no mobile SoC.** `gpu_model` has 29 rows (NVIDIA/AMD/Apple); `tdp_watt` is `NOT NULL` and `GpuSpec.tdp_watt` is `gt=0`, which a phone SoC cannot honestly satisfy (no published TDP). `hardware_class` enum already has `npu` / `integrated_gpu`, unused. | `infra/seed/gpu_models.json`; `infra/migrations/0001_create_hardware_catalog.sql`; `packages/domain-schema/src/gpu_spec.py` | schema gap |
| M8 | **The seed model catalog lacks the mobile SOTAs.** Of 77 `model_release` rows the ≤ 5 B set is Qwen2.5 0.5–3B, Llama 3.2 1B/3B, Phi-3 mini, Gemma 2 2B, Qwen3.5 0.8B/4B, LFM2.5 350M, R1-distill 1.5B. Missing: Gemma 4 E2B/E4B, Gemma 3n, Qwen3.5 2B, LFM2.5 1.2B/2.6B, Ministral 3 3B, Phi-4-mini, Nemotron 3 Nano 4B, MiniCPM5. The **derived** pool (691 models) does know most of them, so `/m/<slug>` pages exist — but a phone user cannot *claim* a run for them on `/submit` because the claim form takes `model_release_id` from the seed catalog. | `infra/seed/model_releases.json`; `apps/web-next/app/submit/submit-client.tsx` | data gap |
| M9 | **`/submit` has no hardware picker and hides the runtime.** Live: the whole capture form is disabled until sign-in; "Hardware — optional" is a free-text input, placeholder `(e.g. 3090 24GB)`, help text "The machine the number was produced on."; the model field is a select ("Select a model…") over the 77 seed ids (M8). A phone owner has no `gpu_model_id` to type, so the claim never gets an engine prior. The API already accepts `inference_runtime_id` (`CreateRunClaimRequest`) but the form never sends it, and the runtime catalog has no mobile runtime anyway (M11) — the app (AI Edge Gallery, PocketPal) can only go in `note`. | `submit-client.tsx` lines 133, 460–469; `apps/public-api/src/schemas/claim_schemas.py`; `qa_s25_submit_hardware_field.png` | UX/data gap |
| M10 | **No measured path from a phone.** `benchmark-probe` detects topology under `cfg!(target_os = "linux" \| "macos")`; a Termux build is `target_os = "android"`, so OS/CPU/GPU detection returns empty strings. The reported/claim path is the only one open to phones today. | `cli/benchmark-probe/src/collect_system_topology.rs` lines 27–63 | capability gap |
| M11 | **Runtime vocabulary is desktop-only.** `runtime_engine` enum / `RuntimeEngine` / `inference_runtimes.json` know llama.cpp, Ollama, vLLM, SGLang, ExLlamaV2, TensorRT-LLM, MLX, LM Studio, ComfyUI. LiteRT-LM, MLC-LLM and GenieX have no id. Gated on S26 (registry instead of enums) — recorded, not fixed by S32. | `packages/domain-schema/src/benchmark_report.py`; `infra/migrations/0002` | deferred |
| M12 | **Layout at 412 px is fine.** web-next is mobile-first (360 px base, min-width queries, tables scroll in their own container); the viewport meta is present. Live: `document.documentElement.scrollWidth` = `window.innerWidth` = 412 on `/`; tap targets and text legible; no clipping on `/`, `/hardware`, `/submit`. | `apps/web-next/app/globals.css`; live console | pass |
| M13 | **No PWA manifest** (`/manifest.json`, `/manifest.webmanifest` → 404); the site cannot be installed to the home screen. Nice-to-have, not in S32. | curl | backlog |

Verdict: the site *renders* well on the phone (M12) but cannot *answer*
for the phone (M1–M3, M7–M9), and its own agent surface sends mobile
readers to a dead URL (M4). The pool has exactly one phone measurement.

## 4. What the S25 Ultra owner can do today (before S32)

1. Install **Google AI Edge Gallery** (Play Store) → download Gemma 4 E2B
   → run the built-in Benchmark. It reports TTFT, decode tok/s and peak
   memory — the same fields `/submit` asks for.
2. Or **PocketPal AI** → pull `Qwen3.5-2B` / `Qwen3.5-4B` / `LFM2.5-2.6B`
   GGUF (Q4) → tok/s is shown per reply.
3. Open `www.bestmodel.run/submit` on the phone and capture the number as
   a **claim** with the app's model page as `source_url`. Today the model
   must be one of the 77 seed ids (M8) and hardware stays free text (M9).
4. For a **signed, validated** run: Termux → build llama.cpp and the probe
   natively — blocked on M10 until S32f lands.

## 5. Owner-visible risks recorded here (not decisions)

- Vendor numbers (§2) are tempting to import as cells. They are
  *claims* with a vendor as claimant: S32d imports them as `run_claim`
  with `provenance.source_url`, community-votable, never leaderboard —
  same rule as the localmaxxing import (S22/S28).
- 12 GB total ≠ 12 GB usable. Until S32f measures peak RSS on the device,
  any "fits" verdict for a phone is `formula` basis with a visible caveat.
- `navigator.deviceMemory` is capped at 8 in Chrome; only User-Agent
  Client Hints (`model` = `SM-S938B`) can tell a 12 GB S25 Ultra from a
  16 GB one — and only when the user grants the high-entropy hint.
