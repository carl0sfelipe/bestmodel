# cli/comfy-lab/ — Map

Executable prompt pack (pre-plan) for the **diffusion vertical** of bestmodel:
a ComfyUI-based probe + workflow analyzer answering "can this machine run this
image model / this workflow, how fast?" — the image-generation counterpart of
the LLM benchmark-probe. No product code exists until the executor sessions run.

- Read order: `README.md` -> `CONTRATO-GLOBAL.md` -> `ESTADO.md` -> `specs/`.
- Executor protocol: `PROMPT-EXECUTOR.md` (one session, one oracle, one
  commit `feat(comfy-S<n>)`).
- This pack is executor territory; it does NOT use the monorepo test flow
  (`make test` / `make gate`) and must not touch anything outside this
  directory — single exception: the S5 symlink into the local ComfyUI
  `custom_nodes/` (see contract §7).
- External prerequisite: a local ComfyUI install (see contract §2). Sessions
  S1–S3 run without it; S4+ requires the server live.
