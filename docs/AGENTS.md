# docs/ — Map

Public planning and reference documents. Historical build session specs live
next to their components (`apps/*/specs/`, Portuguese); everything here is
English.

| File | What it is | When to read |
|---|---|---|
| `architecture.md` | Module dependency graph + code review notes | Before cross-package changes |
| `findings.md` | Numbered calibration findings (F1–F8) + open decisions | Before touching predictors, thresholds, contracts |
| `backlog.md` | Canonical roadmap: tracks A (Local Lab), B (claims/votes), C (virality), D (diffusion) | Before proposing new work |
| `research-2026-08.md` | Competitive landscape teardown + tooling research | Before building CLI v2 / social features |
| `en/submission-tiers.md` | Two-tier reporting design (verified + claimed) | Contract/reporting work |

Rules:

- New operational facts belong here as short, self-contained docs; decisions
  with rationale go in the spec that implements them.
- Calibration data belongs in `findings.md` (numbered, append-only).
