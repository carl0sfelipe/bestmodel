# Pointers (v0, archaic)

A pointer is three fields: **verb · path · one line**. Never paste the
target. Curiosity is not a job — pick a job card, open only that card.

This file is the **read-side** counterpart of the per-folder `AGENTS.md`
checklists (direction v2 D4 = edit-site). D4 says what to *touch together*.
This says what to *open at all*.

v0 is honor system: a markdown catalog. **Fable: refine or reject** — see
§ Fable at the bottom. Do not treat this document as a closed decision.

Verbs:

| Verb | Meaning |
|---|---|
| OPEN | Read this, in the listed order, at the listed budget |
| SKIP | Do not open unless a listed OPEN file names it as required for one decision |
| STALE | Exists, may be useful as history, is **not** operational truth |

---

## Job: fable-escalation (2026-09-19)

This instance. After this card: decide D1–D7; do not write code.

| # | Verb | Path | One line | Budget |
|---|---|---|---|---|
| 1 | OPEN | `docs/POINTERS.md` | This card | this job only |
| 2 | OPEN | `docs/FABLE-BRIEF-2026-09-19.md` | Architecture now + 48h audit + compressed facts | whole |
| 3 | OPEN | `docs/ESCALACAO-FABLE-2026-09-19.md` | Verify / Learn / H1–H4 / **D1–D7** / response shape | whole |
| 4 | OPEN | `docs/HANDOFF-OMARCHY-2026-09-18.md` | Prod machine as of restore | whole (short) |
| 5 | OPEN | `docs/direction-2026-08-29.md` | Your v2 record; still binding where it does not conflict | whole |
| 5b | OPEN | `docs/direction-2026-09-19.md` | v3 record (this escalation's answer) — next escalation starts from here | whole |
| 6 | OPEN | `docs/backlog.md` | Tracks + owner dials | header, B, C, 30/08 dials, S28 — not A1–A11 line by line |

SKIP unless D1–D7 names them:

- `docs/findings.md` · `docs/research-2026-08.md` · `docs/HANDOFF-2026-08-28.md`
- `specs/en/L01-cli-v2-local-lab.md` · `specs/en/L02-social-platform.md` · `specs/engine-epics/**`
- application source

SKIP unless **D3** or **D4** names them:

- `specs/en/S23-per-user-signing-keys.md` — API exists; CLI unwired; table empty
- `docs/direction-2026-08-28.md` § D2 — flywheel: keys before any community campaign

STALE (do not treat as prod):

| Path | Why stale |
|---|---|
| `docs/architecture.md` | 2026-08 graph: no web-next, no OAuth, no Omarchy, no S23 dual-path |
| `docs/en/deploy.md` | Still beelink + Vercel `/v1` rewrite + Pages as DNS cutover |
| `README.md` “What's here” / `apps/web` | Prod front is `apps/web-next` |
| `docs/backlog.md` heading **S30** | That S30 is mural (31/08). OAuth on 19/09 reused the id |
| `deploy/systemd/bestmodel-backup.service` in git | Path `/home/beelink/...`. Live units: `~/.config/systemd/user/` |
| Root `AGENTS.md` “read order” of 7 files | That dump is the anti-pattern this catalog exists to stop |

---

## Job: fable-escalation-2026-09-21

This instance. After this card: decide D1–D8. The owner already authorized
the executor to implement the record in the same turn. Do not invent cells.

| # | Verb | Path | One line | Budget |
|---|---|---|---|---|
| 1 | OPEN | `docs/POINTERS.md` | This card | this job only |
| 2 | OPEN | `docs/ESCALACAO-FABLE-2026-09-21.md` | Verify / Learn / D1–D8 / response shape | whole |
| 3 | OPEN | `docs/handoffs/2026-09-21-music-intent.md` | PR #11 dump; music under audio; no measured cell | whole |
| 4 | OPEN | `docs/handoffs/2026-09-21-3d-gen-intent.md` | rig3d dump; `image-to-3d` root; do not submit | whole |
| 5 | OPEN | `docs/direction-2026-08-29.md` | D1 chronic cause, D2.5 modality registry | D1–D2 only |
| 6 | OPEN | `docs/direction-2026-09-19.md` | v3 D4 hand-edit of PR #11 is the line under review | D4 + order row 7 |

SKIP: application source, except the paths named in the escalation §2.
SKIP: `docs/ESCALACAO-FABLE-2026-09-19.md` (already decided; do not re-litigate D1–D7).

---

## Job: zcode-execute

After Fable's record is owner-approved. Open the story spec + the nearest
`AGENTS.md` to the edit + the D4 checklist there. Do not re-ingest the
escalation.

| Verb | Path | One line |
|---|---|---|
| OPEN | `docs/direction-2026-09-19.md` | current record: order table + sizes; H6 check before owner enrols a passkey |
| OPEN | the spec Fable/owner named | acceptance commands live there |
| OPEN | nearest `AGENTS.md` to the files you will touch | edit-site checklist |
| OPEN | `docs/HANDOFF-OMARCHY-2026-09-18.md` | only if the change is prod/ops |
| SKIP | `docs/ESCALACAO-FABLE-*.md` | already decided |
| SKIP | `docs/research-2026-08.md` | not an execute input |

---

## Job: prod-ops

| Verb | Path | One line |
|---|---|---|
| OPEN | `docs/HANDOFF-OMARCHY-2026-09-18.md` | current host |
| OPEN | `deploy/docker-compose.omarchy.yml` | PGDATA + tunnel override (untracked until owner reviews) |
| SKIP | `docs/en/deploy.md` | STALE host and front topology |
| SKIP | `deploy/systemd/*` in git | live units are under `~/.config/systemd/user/` |

---

## Job: cold-start (any agent, public clone)

Unchanged: `docs/agent-quickstart.md`. That path is for *running the
probe*, not for strategy.

---

## How to add a pointer (v0)

1. One row. Path must exist, or the row says `untracked` / `outside repo`.
2. The one-liner is the whole comment. No second paragraph in the catalog.
3. Mark STALE in the **same** change that made the file wrong — otherwise
   the next expensive model will ingest a lie. (Honor system in v0.)
4. A new Fable escalation **copies a job card**; it does not paste HANDOFF
   or direction into the prompt.

---

## § Fable — refine or reject (not D1–D7)

The owner liked this. v0 is deliberately dumb (a table). Your v2 D1 said
**recorded knowledge without a mechanism at the point of change does not
alter agent behavior.** This catalog is currently recorded knowledge.

Please answer, short, in the same decision record (a line under D1–D7 is
enough — not a new epic unless you decide it is):

1. **Standing convention, or per-escalation brief only?** Root `AGENTS.md`
   still tells every agent to ingest seven files. v0 weakens that in prose.
   Keep / replace / gate it?
2. **Mechanism vs honor?** Presence-grep of job cards (like S25c greps
   AGENTS.md headings)? A `STALE:` header the gate fails on if architecture
   still says beelink? Or prose is enough here because the reader is you,
   once, and ZCode already has D4 at the edit site?
3. **Who marks STALE, in which commit?** Same-commit as the fact change
   (lockstep with FakeDatabase), or a periodic sweep (will rot)?
4. **Jobs vs folders?** D4 mapped *directories*. This maps *jobs*. Do they
   stay two catalogs, or does each `AGENTS.md` gain an OPEN/SKIP card?
5. **`llms.txt`?** External agents vs Cursor Fable — same pointer protocol
   or a different budget?

Rejecting v0 is a valid answer. Adopting it as “one extra heading in
AGENTS.md, no gate” is also a valid answer. Size it.
