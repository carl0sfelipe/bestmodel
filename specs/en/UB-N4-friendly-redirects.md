# Task: friendly redirects for the URLs people and agents guess

OBJETIVO: stop 404s on the obvious short URLs. Work only in apps/web-next. Local commits fine, never push.

## Dados verificados
- 2026-10-05 against https://bestmodel.run: `/cloud` 404, `/anchors` 404, `/agent` 404, `/api` 404. The real pages are `/cloud-anchors` (rented-GPU runs) and `/llms.txt` (agent surface; served from `apps/web-next/public/llms.txt`).
- `apps/web-next/app/api/` exists with a sub-route (`app/api/em-breve`); only the exact path `/api` may redirect, never `/api/:path*`.
- `apps/web-next/next.config.ts` has `rewrites()` but no `redirects()`.
- Tests run with `node --experimental-strip-types --test lib/*.test.ts` from apps/web-next (no install).

Nao invente numero, prazo ou fonte alem dos listados.
NUNCA use declare const como workaround — importe de verdade.

## PROIBIDO
push. deploy. Redirecting any `/api/...` sub-path or `/v1/...`. Changing `rewrites()`. Portuguese in code or comments.

## PASSOS
1. `lib/friendly-redirects.ts`: export `FRIENDLY_REDIRECTS` = array of `{ source, destination, permanent: false }`:
   - `/cloud` → `/cloud-anchors`, `/anchors` → `/cloud-anchors`, `/cloud-anchor` → `/cloud-anchors`
   - `/agent` → `/llms.txt`, `/agents` → `/llms.txt`, `/api` → `/llms.txt`
   - and a pure `resolveFriendlyRedirect(pathname): string | null` (exact match, trailing slash tolerated, case-insensitive).
2. `next.config.ts`: `async redirects() { return FRIENDLY_REDIRECTS; }` importing from the lib file.
3. `lib/friendly-redirects.test.ts` (node:test): each source resolves; `/cloud/` resolves; `/CLOUD` resolves; `/api/em-breve` → null; `/v1/match` → null; `/cloud-anchors` → null (no loop); every destination is not itself a source.

VERIFICACAO: cd apps/web-next && node --experimental-strip-types --test lib/friendly-redirects.test.ts

## Oraculo
- comando: cd apps/web-next && test -f lib/friendly-redirects.test.ts && node --experimental-strip-types --test lib/*.test.ts && grep -q "redirects()" next.config.ts
- exit esperado: 0

## Barra
- nome: node:test apps/web-next/lib
- como fetchar: cd apps/web-next && node --experimental-strip-types --test lib/*.test.ts
- como comparar: all green, next.config has redirects()
