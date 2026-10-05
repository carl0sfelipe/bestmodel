# Task: llms.txt snapshot totals must match stats.json (and never drift again)

OBJETIVO: the "Snapshot totals" section in both llms.txt copies is stale (says 2026-08-13 / runs 4849, models 527, rigs 147) while the source of truth apps/web/data/derived/stats.json says 2026-09-18 / runs 8230, models 686, rigs 184. Fix both copies and add a test that fails the suite on any future drift. Local commits fine, never push.

## Dados verificados
- `apps/web-next/public/llms.txt` has the section heading `## Snapshot totals (apps/web/data/derived/stats.json, 2026-08-13)` followed by `- runs: 4849`, `- models: 527`, `- rigs: 147`.
- `apps/web/site/llms.txt` has the same stale section with the same date and numbers.
- Root `llms.txt` has NO "Snapshot totals" section (leave it alone).
- `apps/web/data/derived/stats.json` has `"snapshotAt": "2026-09-18T17:08:19.808Z"` and `totals: { runs: 8230, models: 686, rigs: 184 }`.
- web-next lib tests run with `node --experimental-strip-types --test lib/*.test.ts` from `apps/web-next`, no install needed (existing lib tests use only node builtins).

Nao invente numero, prazo ou fonte alem dos listados.
NUNCA use declare const como workaround — importe de verdade.

## PROIBIDO
push. Modifying `apps/web/data/derived/stats.json` (it is generated; it is the source of truth). Lockfile changes. Portuguese in code or comments. Touching `apps/api`, `cli/`, `Cargo.*`, `deploy/`, `infra/`.

## PASSOS
1. New `apps/web-next/lib/llms-totals.test.ts` (node:test, only `node:fs`, `node:path`, `node:assert` — zero deps):
   - read `public/llms.txt` (relative to the lib file) and `../../web/data/derived/stats.json`;
   - assert the `## Snapshot totals (..., <date>)` heading date equals `snapshotAt` sliced to YYYY-MM-DD;
   - assert each of `runs:`, `models:`, `rigs:` in that section equals the matching `totals` value from stats.json;
   - assert `apps/web/site/llms.txt` carries the same three numbers and date as `public/llms.txt`.
2. Update BOTH `apps/web-next/public/llms.txt` and `apps/web/site/llms.txt`: heading date `2026-09-18`, `- runs: 8230`, `- models: 686`, `- rigs: 184`. Change nothing else in these files.
3. Run the full lib suite from apps/web-next to prove no regression.

VERIFICACAO: cd apps/web-next && node --experimental-strip-types --test lib/llms-totals.test.ts && grep -q "runs: 8230" public/llms.txt && grep -q "runs: 8230" ../web/site/llms.txt

## Oraculo
- comando: cd apps/web-next && test -f lib/llms-totals.test.ts && node --experimental-strip-types --test lib/*.test.ts && grep -q "runs: 8230" public/llms.txt && grep -q "2026-09-18" public/llms.txt && grep -q "runs: 8230" ../web/site/llms.txt
- exit esperado: 0

## Barra
- nome: node:test apps/web-next/lib (incl. llms-totals)
- como fetchar: cd apps/web-next && node --experimental-strip-types --test lib/*.test.ts
- como comparar: all green AND both llms.txt show runs 8230 / models 686 / rigs 184 / 2026-09-18
