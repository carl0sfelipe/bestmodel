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
| `architecture.md` | Module dependency graph + code review notes (**stale** em web-next/OAuth/Omarchy — usar o brief) | Before cross-package changes |
| `findings.md` | Numbered calibration findings (F1–F8) + open decisions | Before touching predictors, thresholds, contracts |
| `backlog.md` | Canonical roadmap: tracks A (Local Lab), B (claims/votes), C (virality), D (diffusion) | Before proposing new work |
| `research-2026-08.md` | Competitive landscape teardown + tooling research | Before building CLI v2 / social features |
| `agent-quickstart.md` | Cold-start runbook: build, detect hardware, rank models offline, run the probe | First action on a fresh machine/checkout |
| `QA-MOBILE-DOGFOOD-2026-09-20.md` | Galaxy S25 Ultra dogfood: device facts, vendor on-device numbers (labelled), findings M1–M14 on the live site and CLI | Job `mobile-s32`, before executing any S32 story |
| `incidents/` | Incident diary entries in the llms.surf format (frontmatter `id/titulo/data/recorrivel/regra/status/interage_com` + `workarounds` list; Portuguese, as the private diary they are copied to). Entry `2026-09-20-cli-nao-responde-hardware-fora-do-catalogo-ia-fez-workaround.md`: CLI/site could not answer for a phone, an agent answered by workaround (W1–W8) | When a product gap was papered over by an agent — record it here so recurrences become mechanisms |
| `en/submission-tiers.md` | Two-tier reporting design (verified + claimed) | Contract/reporting work |

Rules:

- New operational facts belong here as short, self-contained docs; decisions
  with rationale go in the spec that implements them.
- Calibration data belongs in `findings.md` (numbered, append-only).
- When a doc stops being operational truth, add a STALE row to `POINTERS.md`
  in the same change (v0 honor system; Fable may turn this into a gate).
