# apps/web/ — Map

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
