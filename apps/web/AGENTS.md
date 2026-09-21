# apps/web/ — Map

> ARCHIVED (2026-09-21, L04 D5/S36): `site/` is a frozen visual reference —
> it is NOT deployed anywhere. The published GitHub Pages output is a redirect
> to the canonical host `www.bestmodel.run` (web-next), which now owns the
> `?as=` dual view. The console (`console/`) is the one live surface here.
> Do not build new site features in this tree.


Executable prompt pack (pre-plan) for the public bestmodel website: the three
design prototypes in `prototypes/` wired to real community data harvested
from localmaxxing's public API. No product code exists until the executor
sessions run.

- Read order: `README.md` -> `CONTRATO-GLOBAL.md` -> `ESTADO.md` -> `specs/`.
- Executor protocol: `PROMPT-EXECUTOR.md` (one session, one oracle, one
  commit `feat(web-S<n>)`).
- This pack is executor territory (cheap model via oracfit); it does NOT use
  the monorepo test flow (`make test` / `make gate`) and must not touch
  anything outside this directory.
- `prototypes/` is the frozen visual spec — never edit.
- Reader journey (human vs agent) lives in `site/assets/journey.js` +
  `html[data-journey]`. Distinct from the human goal/hardware switcher.
