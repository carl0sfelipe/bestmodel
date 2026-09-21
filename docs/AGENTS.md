# docs/ — Map

Public planning and reference documents. Historical build session specs live
next to their components (`apps/*/specs/`, Portuguese); everything here is
English.

| File | What it is | When to read |
|---|---|---|
| `POINTERS.md` | Job cards: OPEN / SKIP / STALE. Read-side catalog (v0). | Before any other docs file — pick a job, follow only that card |
| `FABLE-BRIEF-2026-09-19.md` | Pacote mínimo para o Fable (arquitetura atual + auditoria 48h). Começa aqui numa escalada. | Job `fable-escalation`, after POINTERS |
| `ESCALACAO-FABLE-2026-09-19.md` | Pedido D1–D7 (Omarchy + OAuth); Fable decide, não implementa | Escalada estratégica 19/09 |
| `HANDOFF-OMARCHY-2026-09-18.md` | Retrato de prod no desktop Omarchy (substitui o HANDOFF do beelink) | Estado da máquina |
| `direction-2026-09-19.md` | Fable v3 decision record (D1–D7 sized + execution order + H5–H12) | Before executing anything post-incident |
| `ESCALACAO-FABLE-2026-09-21.md` | Clarify: one way to add an intent (music + image-to-3d). Fable decides, executor implements the record | Job `fable-escalation-2026-09-21` |
| `handoffs/2026-09-21-music-intent.md` | Dump of draft PR #11. Not implementation | That escalation only |
| `handoffs/2026-09-21-3d-gen-intent.md` | Dump of the rig3d image-to-3d session. Not implementation; do not submit | That escalation only |
| `architecture.md` | Module dependency graph + code review notes (**stale** em web-next/OAuth/Omarchy — usar o brief) | Before cross-package changes |
| `findings.md` | Numbered calibration findings (F1–F8) + open decisions | Before touching predictors, thresholds, contracts |
| `backlog.md` | Canonical roadmap: tracks A (Local Lab), B (claims/votes), C (virality), D (diffusion) | Before proposing new work |
| `research-2026-08.md` | Competitive landscape teardown + tooling research | Before building CLI v2 / social features |
| `agent-quickstart.md` | Cold-start runbook: build, detect hardware, rank models offline, run the probe | First action on a fresh machine/checkout |
| `en/submission-tiers.md` | Two-tier reporting design (verified + claimed) | Contract/reporting work |

Rules:

- New operational facts belong here as short, self-contained docs; decisions
  with rationale go in the spec that implements them.
- Calibration data belongs in `findings.md` (numbered, append-only).
- When a doc stops being operational truth, add a STALE row to `POINTERS.md`
  in the same change (v0 honor system; Fable may turn this into a gate).
