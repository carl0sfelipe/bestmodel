# Task: /wall agent view — English miss message, rig-aware suggestions, toy filter gaps

OBJETIVO: fix three defects in apps/web-next found on 2026-10-05 by calling https://bestmodel.run/wall?rig=a100-80gb&as=agent and /wall?as=agent.

## Dados verificados
- `apps/web-next/app/wall/page.tsx` prints `rig não encontrado: …` and `10 slugs de rig mais parecidos:` (Portuguese on an English site).
- `unknownRig` in `apps/web-next/lib/wall-filter.ts` uses `sugerirSlugs` (plain edit distance). For `a100-80gb` the top suggestion is `pro-64gb`-like noise, while `h100-80gb` (same memory size, same vendor class) is the useful answer.
- `apps/web/data/derived/models.json`: `delphi-suite-stories-llama2-50k` and `ggml-org-models-moved` have `category: "chat"`, `paramsB: null`. They top the default /wall ranking (36,715 and 16,740 tok/s) even though the agent view says "Default ranking excludes <1B and toy/tinystories".
- Tests run with `node --experimental-strip-types --test lib/**/*.test.ts` from `apps/web-next` (no install needed).

## PROIBIDO
- push, deploy, editing anything outside `apps/web-next/`.
- Changing the honesty ladder text or any number.
- Portuguese in identifiers, comments or user-facing strings.
- `declare const` or type-casts to silence errors.

## PASSOS
1. Rename `lib/sugerir-slugs.ts` → `lib/suggest-slugs.ts`, `sugerirSlugs` → `suggestSlugs`, parameter `todos` → `candidates`; same for the test file. Update every import (`app/m/[slug]/page.tsx`, `lib/wall-filter.ts`).
2. Add `suggestRigs(query, keys, n)` in `lib/suggest-slugs.ts`:
   - Parse the memory token `(\d+)gb` and the multi-GPU suffix `-x(\d+)` from query and candidate.
   - Rank: same memory AND same GPU count first; then same memory; then shared dash-separated tokens (more is better); then edit distance. Stable tie-break by key.
   - `unknownRig` uses `suggestRigs` (keep n = 10).
3. In `app/wall/page.tsx` agent view: `rig not found: <key>` and `Closest rig keys:`.
4. In `lib/wall-filter.ts` `isToyOrTinyMarked`: also mark as toy when the slug/displayName/hfId contains `stories-` or `-stories` as a whole dash token sequence (e.g. `stories-llama2-50k`), or when the hfId ends with `/models-moved`.
5. Tests (node:test, in the existing test files):
   - `suggestRigs("a100-80gb", ["pro-64gb","h100-80gb","h200-sxm-141gb","rtx-3090-24gb","rtx-3090-24gb-x2"])[0] === "h100-80gb"`.
   - `suggestRigs("rtx-3090-24gb-x4", [...same list..., "rtx-3090-24gb-x4b"])` ranks `rtx-3090-24gb-x2` above `pro-64gb`.
   - `isDefaultRankingExcluded` is true for the two models above (use their real fields) and false for `{slug:"qwen-qwen3-8-27b", category:"chat", paramsB:27}`.
   - The unknown-rig test asserts the English wording via a pure helper you extract: `formatRigMiss(miss): string[]` in `lib/wall-filter.ts`, used by the page.

VERIFICACAO: cd apps/web-next && node --experimental-strip-types --test lib/**/*.test.ts && ! grep -rn "não encontrado\|sugerir\|parecidos" app lib

## Oraculo
- comando: cd apps/web-next && node --experimental-strip-types --test lib/*.test.ts && ! grep -rqn "não encontrado\|sugerir\|parecidos" app lib && grep -q "suggestRigs" lib/suggest-slugs.ts && grep -q "Closest rig keys" lib/wall-filter.ts
- exit esperado: 0

## Barra
- nome: node:test in apps/web-next/lib
- como fetchar: cd apps/web-next && node --experimental-strip-types --test lib/*.test.ts
- como comparar: all tests pass, no Portuguese strings left in app/ or lib/
