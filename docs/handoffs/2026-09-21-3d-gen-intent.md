# Handoff — 3D-gen intent (rig3d × bestmodel.run) — 2026-09-21

Source session: the ZCode session that started the 3D-generation intent (rig3d project) and drove it to: TRELLIS local pipeline on the owner's RTX 3090, 16 generated assets, wizard UI with per-item photos, mechanical gates, and a staged (NOT submitted) bestmodel intake for the new image-to-3d category.

Receiver note (this monorepo, 2026-09-21): copied from the source dump. The file on the source machine is `rig3d/docs/handoffs/2026-09-21-3d-gen-intent.md` and was left uncommitted. This copy is the Clarify input. It is not implementation, and it does not authorize submitting `bestmodel-intake/submission.json`.

## 1. Session

- Repo: `/home/carlos/.zcode/workspace/default/rig3d` (standalone repo, born this session; NOT the llms.surf repo, NOT the bestmodel monorepo).
- Branch: `main`.
- HEAD: `96b9f62` "painel de detalhes: seletor de VERSOES por asset + abrir no Blender".
- `git status --short` at dump time: `M components/ram-32gb-kingston.json`
- Stash: empty.
- Uncommitted diff (full, small): `mesh_glb` changed from `meshes/ai/ram-32gb-kingston.glb` to `gauntlet/rejected/ram-32gb-kingston-parametrico.glb`. Notes say the owner rejected TRELLIS for RAM (C1/C2) and the parametric mesh is a bake. This pending change is almost certainly the owner clicking "usar esta versão" on the parametric preview (`/api/use_version` writes exactly this). It contradicts his verbal "RAM ficou ruim". Needs his A4 confirmation. Do not silently commit or revert it.
- The handoff file itself was intentionally untracked on that repo.

## 2. What the owner actually asked

Quotes and paraphrase, in order. Owner words, then one idea that was not yet a request.

- "quero fazer dogfooding duplo usar o llms.surf para batchear uma run na 3090 para gerar todos assets que der ao mesmo tempo em que faz dog fooding no bestmodel.run e cria a nova subcategoria image do 3d model" — plan it and produce an escalation prompt for Fable's blessing.
- "pare essa automacao que ta iniciando o exl e qualquer coisa usando a placa para deixala livre para gerar o arquivo 3d" — stop EXL3/automation.
- "quero colar da area de transferencia ao clicar no card" + "clicou ja abre o modal com a foto colada e o dropdown" — paste-photo UX per item.
- "quero que no detalhes mostre todas as versos que voram geradas para eu escolher a melhor o blender ta instalado para eu poder abrir os 3d e editar na mao?" — versions selector + Blender GUI access.
- Review of the first batch: cooler, HDD, B450 Aorus, B450 Mortar, PSU Aorus, and riser cable are good; SSD and RAM are wrong (too thick) and must be redone; the case should be open so parts can go inside; leave cables for last.
- Later, after seeing retries: "achei as primeiras versoes melhores" (batch TRELLIS v1 preferred over the 20-steps retry).
- OWNER IDEA (not yet a request): use Blender to hand-refine assets. He wanted "blender mcp". In-session clarification: no Blender MCP is connected; bpy headless scripting is the working equivalent.

## 3. Definition reached

- Category id: `image-to-3d` (Fable decision record §5.1 on that host: ROOT category, not a subcategory of anything else).
- UI name: ABSENT (no UI/category work landed in the bestmodel monorepo).
- Modality: own root category, sibling of chat/code/image/audio/video.
- Models cited: TRELLIS-image-large (Microsoft, MIT, local on RTX 3090, HF snapshot cached) — the only model measured. Mentioned and excluded: Hunyuan3D (ZeroGPU quota), parametric bpy builders for RAM/SSD (owner rejected the look), procedural cables (deferred, not in slice), ComfyUI (unrelated vertical).
- Out of scope this slice: cable procedural modeling. RAM/SSD TRELLIS regeneration was forbidden by Fable then re-authorized verbally by the owner ("usa o trellis pra fazer tudo"). Net state: RAM/SSD assets on disk are the BATCH v1 TRELLIS versions (owner prefers them over both the 20-steps retry and the parametric ones). Quality still "grosso" per owner.

## 4. Limits map

| # | File | Restriction found | Intended change | Status |
|---|---|---|---|---|
| L1 | `apps/pool-backend/src/db.py:18` (bestmodel) | `CHECK(category IN ('chat','code'))` rejects an image-to-3d submission | extend CHECK to include `image-to-3d` (+ migration) | NOT MADE (read-only inspection) |
| L2 | `apps/web-next/app/home-client.tsx:23-28` | INTENTS has chat/code/image/audio/video; vision has `category: null`; no 3D intent | add intent row (`image-to-3d`, "image → 3D model") + wire category | NOT MADE |
| L3 | `CONTRATO-GLOBAL.md` | NOT FOUND in bestmodel root (quick find) | UNKNOWN if it constrains categories | NOT INSPECTED |
| L4 | intake API category validation | UNKNOWN — not inspected beyond the DB CHECK | verify intake router accepts the new category | NOT INSPECTED |
| L5 | metric contract | tokens/s is the pool's native metric; FORBIDDEN for image→3D (Fable 5.2) | sec/asset + VRAM peak + quality gates instead | CONTRACT AGREED (Fable), schema staged locally only |
| L6 | rig3d dims | 3 components still without sourced dims (r43sg-adtlink, frame-12gpu-flytec, psu-hq-2000wp) | source or halt | PARTIAL (halt is current state) |
| L7 | GPU exclusivity | EXL3 stopped since the batch (owner-authorized); Vigília automation PAUSED; `scripts/restore_exl3.sh` ready | restore EXL3 when owner says | PENDING OWNER |
| L8 | A4 reviews pending | 3090 v1 vs v2, case-open verdict, RAM/SSD "grosso" acceptance | owner A4 in wizard panel | PENDING OWNER |
| L9 | Blessed artifacts | The Fable-approved decision record + 6 specs + `rig3d-oracle/` + `bestmodel/image-to-3d/` validator described in the escalation reply are ABSENT on this host | re-sync or port them | NOT DONE |

Receiver correction, not part of the source dump: L3 does exist in this monorepo at `apps/pool-backend/CONTRATO-GLOBAL.md` line 64, same `CHECK(category IN ('chat','code'))`. L4 in this monorepo is `scenario_kind` (video is a first-class scenario on the Postgres intake). There is no `image-to-3d` scenario kind here.

## 5. Files created or edited

All inside the rig3d repo unless noted.

- Core: `src/rig3d/{schema,budget,build_blender,report,cli,inventory,compare}.py`
- Generation: `tools/gen3d.py`, `tools/gen_local_trellis.py`, `tools/fix_glb_materials.py`, `tools/normalize_glb.py`, `tools/refine_case.py`, `tools/open_case.py`, `tools/preview_glb.py`
- Builders: `builders/ram_parametric.py`, `builders/ssd_m2.py`, `meshes/rtx-3090.py`
- Oracles/gates: `tests/{test_budget,test_compare,test_gauntlet}.py`, `tests/test_oracle.sh`, `tests/test_gauntlet.sh`, `examples/_gauntlet-node3.json`
- Product/UI: `serve.py`, `viewer/index.html`
- Data: `components/*.json`, photos, `setup/`, `spec/gauntlet-visual.md`, `bestmodel-intake/submission.json` (STAGED, not submitted), `specs/rig3d-assets-batch.md`, `specs/3d-gen-gauntlet.md`, scripts, gauntlet state, `meshes/ai/*.glb` (16 assets + v2)
- Artifacts: `out/` + `out_dc/` — regenerable

## 6. Metric contract

Shown for image-to-3d: sec/asset (median + per-item), VRAM peak MiB, quality gates (dims audit worst %, mean luminance > 40/255, metallic = 0 on all materials), input photo count, seed/steps, glb sha256.

Prohibited: tokens/s or any LLM-derived metric.

Honesty basis: this run = `reported` (1 run) until pool ≥ 3 measured.

## 7. Honesty audit

- MEASURED: batch 10/10 rc=0; per-item wall times from logs (120–241 s clean); VRAM peak 20,177 MiB sampled at 1 Hz; 16 glb sha256; dims audit 0.00% worst deviation on sourced axes; luminance 111–115.
- DERIVED (declared): RAM heights 34.1/34.0 mm via rembg-mask scale against known 133.35 mm length; SSD identified as Kingston NV3 M.2 2280 (80×22×3.5) by reading the owner's photo.
- THICKNESS ~7 mm on RAMs = declared modeling choice, `[TO MEASURE]` with caliper — flagged in component JSON.
- INVENTADO: none knowingly. One earlier vision-model hallucination of a "4× 3090 rig" in an unrelated photo was caught, logged in `spec/gauntlet-visual.md`, and neutralized by the neutral-prompt rule.

These numbers live in rig3d. They are not in this monorepo. Do not copy them into pool JSON from this handoff.

## 8. Where the session got lost

- Last stable decision: Fable decision record (§5.1–5.6 approved: root category `image-to-3d`; sec/asset+VRAM+gates shown as `reported` (1 run); schema-first; trellis-lab adapter to backlog; EXL3 window authorized with flock/trap/restore).
- THE LIMIT: the blessed artifacts (decision record, 6 specs, `rig3d-oracle/verify_assets.py`, `bestmodel/image-to-3d/` validator) never materialized on this host; and the bestmodel monorepo changes (category migration L1, UI intent L2) were never made. The DB CHECK still rejects the category, so the staged submission cannot be ingested.
- Left without answer: (a) owner A4 on 3090 v1-vs-v2 and case-open; (b) whether the pending `mesh_glb` → parametric click on RAM stands; (c) RAM/SSD realism path; (d) EXL3 restore timing.

## 9. Next step (do not execute from this handoff alone)

Port/confirm the blessed artifacts, then make the bestmodel monorepo accept `image-to-3d`: extend the L1 CHECK + migration, add the L2 intent row, verify intake validation (L4), and only then submit the staged `bestmodel-intake/submission.json` (`reported`, 1 run, evidence hashes). In parallel, rig3d side: owner A4s, restore EXL3 via `scripts/restore_exl3.sh`, and keep the gauntlet loop (A0–A4) as the acceptance path for every future asset.

## Music

ABSENT — this conversation never touched the music workstream.
