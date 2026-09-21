# L06 — Human craft pass: de-slop the human view of web-next

> Escalation source: owner, 2026-09-21 v3 ("the version that's supposed to be for
> humans still feels off — I, a human, still find it strange. Use
> github.com/nutlope/hallmark + github.com/petergyang/no-ai-slop to make a human
> version that looks genuinely hand-made"). Scope: **only the human default view
> of web-next**. The `?as=` dual-view contract and the agent twins (L04 S32) are
> untouched — the machine surface may be uniform; the human one must not read as
> a template.

This file is the epic umbrella: it carries the decision record, the design
fingerprint (the DNA this house keeps), and the map/order of the stories
(S43–S47). Each story is a self-contained spec with a mechanical `## Oráculo`
for the copy gates (grep) plus a documented hallmark self-critique for the
design gates (no mechanical oracle exists for taste — the implementer records it
in the PR, per the skill's pre-emit critique).

## Validation (spot-checked on `origin/main`, 2026-09-21)

- Same macrostructure on every route: `/wall`, `/hardware`, `/track-record`,
  `/console` all open with `page-head` = amber uppercase `.kicker` + an `<h1>`
  broken mid-headline by `<br/>` + a muted paragraph + `btn primary`/`btn`, then
  a `.card`/`.wall-row` grid at `border-radius:14px`.
- Verified `<br/>`-split headlines: "What the community<br/>actually measures."
  (`/wall`), "Trust is a ladder,<br/>climbed by verified acts." (`/track-record`),
  "Reference rigs,<br/>with a real track record." (`/hardware`).
- One palette/type everywhere (`app/globals.css:2`): `--bg:#0B0C0E`,
  `--amber:#E0A458`, `--hair:rgba(255,255,255,.08)`, Inter Tight + JetBrains
  Mono — the on-distribution default hallmark warns about.
- The craft DNA is not missing, it was flattened: the frozen archive
  `apps/web/site/` still holds the hand-built ecosystem SVG (the
  "can-i-run-it engine" node graph), the `$bestmodel.run` mark, the reader/agent
  twin, and journey.js's "else: ask — do not guess" voice. Even the archive
  headline ("This isn't a database. It's the operating system…") is itself a
  binary contrast to drop.

## What each skill contributes to these specs

- **hallmark** (design): structural variety over visual variety — two pages must
  not share the hero→cards→CTA rhythm; per-page macrostructures on one locked
  design system; pre-emit six-axis self-critique (Philosophy, Hierarchy,
  Execution, Specificity, Restraint, Variety); named gates cited below. The
  implementer runs `npx skills add nutlope/hallmark` and applies the verbs at
  build time; these specs pre-decide the fingerprint and record the gates.
- **no-ai-slop** (copy): a ban-list of writing patterns (binary contrasts,
  colon reveals, faux-insight setups, throat-clearing, grandiloquence, banned
  words) that translate into **grep-able copy gates** per story.

## Design fingerprint (the DNA this house keeps)

- **Genre: editorial-technical, not atmospheric.** The terminal/mono voice is
  the brand soul (present since the archive); the flattening came from the
  atmospheric dark-AI-tool default, not from the terminal DNA. Keep the DNA,
  drop the default.
- **One locked design system, per-page macrostructures.** Following hallmark's
  `design.md`-managed multi-page model: pages **share** the token system (so the
  site is coherent) and **differ** on macrostructure (so no page reads as a
  colour-swap of another). A `design.md`/`tokens.css` is the single source; each
  page picks a distinct macrostructure:
  - `/` — **Workbench**: the existing intent×rig×quant×context configurator with
    the live basis-declaring verdict IS the hero; it is a real signature, not
    slop. Keep it, drop the surrounding templated scenes.
  - `/cli` — **Long Document / Step Sequence**: a runbook reads as a document of
    real commands, not a marketing hero (also serves L04 S33 honesty).
  - `/wall` — **Tabular Spec-Sheet**: the pool is a spec sheet; lead with the
    data table, minimal hero.
  - `/claims` — **Feed / Stat-Led**: a feed of claims with provenance and basis,
    structurally distinct from the pool table.
- **Palette + type:** keep the dark terminal base and JetBrains Mono as the
  brand voice-carrier (the `$bestmodel.run` mark, the honesty badges) — the slop
  is the macrostructural sameness and the copy, not the palette. Amber stays as
  the identity accent. The custom-theme depth (a tuned OKLCH palette) is an
  **option** the implementer may take under hallmark if, after the structural
  and copy fixes, the palette still reads generic — but the default is
  DNA-locked, not a repaint.
- **Signature move to reinstate:** the hand-built ecosystem SVG from the archive
  as the home craft anchor — a real, hand-made diagram, not a card grid.
- **Nav/footer off the AI fingerprints:** move away from N1a (wordmark + inline
  links) and Ft3 (4-column link farm) toward a mono masthead and a statement
  footer (hallmark defaults N1a/Ft3 OFF as the most-recognised tells).

Why this reads as *this* house and no one else: the honesty ladder rendered as
structure (a spec sheet for the pool, a runbook for the CLI, a live basis-
declaring workbench for the home), the terminal `$bestmodel.run` voice, and the
hand-drawn ecosystem diagram — none of which a template ships.

## Decision record

Size legend: **story** · **line** (backlog one-liner) · **rejection**.

### D1 — Rework the 4 human-core routes, not all 13 — **epic → S43–S46**
Decision: hand-craft `/`, `/cli`, `/wall`, `/claims` in V1 (the routes a human
visitor actually lands on). The console's human craft is **owned by L04 S34**
(social surface) and adopts this system — not re-specced here. The remaining 8
routes inherit the locked tokens and get a hand-craft **backlog line** (S47).
Why: right-sizing — craft the entry surfaces first; the rest inherit coherence
cheaply. Kills: the "redesign everything at once" scope that stalls.

### D2 — One locked design system, distinct macrostructure per page — **epic (fingerprint above)**
Decision: a shared `design.md`/`tokens.css` (coherence) + a different hallmark
macrostructure per page (variety), per the fingerprint. Kills: the universal
`page-head` + `.card`-grid template that makes all pages colour-swaps.

### D3 — Rewrite the copy with no-ai-slop, honesty intact — **story (per page) + S47 gate**
Decision: rewrite headlines/body to drop the ban-list patterns (mid-headline
`<br/>`, binary contrasts, colon reveals, grandiloquence, banned words) while
every number keeps its basis. A repo-wide grep gate (S47) institutionalizes it.
Why: the copy is the loudest tell; slop-free is not warmer marketing — over-
sweetening the text past the data is the same sin inverted (§5). Kills: the
templated poetic two-line headlines.

### D4 — Reinstate the hand-built ecosystem diagram on `/` — **story (in S43)**
Decision: port the archive's ecosystem SVG (the node graph) as the home craft
anchor, redrawn to current data, no fabricated nodes.
Why: it is the single strongest "made, not generated" element and it is already
this brand's DNA. Kills: the generic 3-card "stats" grid as the home's proof.

### D5 — Keep the terminal palette + type; custom repaint is optional — **line**
Decision: the dark base + JetBrains Mono + amber stay the system; a tuned OKLCH
custom theme is an implementer option under hallmark only if the palette still
reads generic after D2/D3. Not mandated.
Why: the palette is brand DNA, not the slop; forcing a repaint risks losing the
identity the owner says must survive (§5).

### D6 — Reject a framework change and any agent-twin redesign — **rejection**
Decision: Next.js stays; the console stays a static app; the `?as=` mechanism,
middleware, and agent twins (L04 S32/S35) are untouched; no heavy motion (cut
the per-word stagger reveal — a tell — keep reduced-motion-safe fades).
Why: §5 non-negotiables; the machine surface may be uniform, only the human view
is in scope. Kills: scope creep into the contract and the twins.

### D7 — `llms.txt` updated in the same cut as any route/copy contract change — **contract (D9 of the house)**
Decision: if a rework changes a contractual route or the human-tour copy that
`llms.txt` declares, update `apps/web/site/llms.txt` in the same PR.
Kills: contract drift between the site and its agent map.

### D8 — Keep L04 (S32–S36) oracles green; amend by declaration where copy moves — **contract**
Decision: the human-craft rework must not break L04 oracles. The `/cli` copy
keeps the literal strings S33-c2 greps (`benchmark-probe`, `agent-smoke` — they
are the real commands anyway); the `data-view="human"` marker (S32) stays on
every reworked page. If any L04 criterion greps human copy this rework removes,
amend that criterion in the same PR with a one-line reason (house pattern
S33-c3/S36-c2).
Why: the two clusters must not fight. Kills: a green-turned-red L04 gate.

## Story map

| Story | Title | Size | Depends on |
|---|---|---|---|
| S43 | Design system (`design.md`/tokens) + `/` home human-craft (Workbench + ecosystem diagram) | story | — |
| S44 | `/cli` human-craft (Long Document / Step Sequence) | story | S43 |
| S45 | `/wall` human-craft (Tabular Spec-Sheet) | story | S43 |
| S46 | `/claims` human-craft (Feed / Stat-Led) | story | S43 |
| S47 | Repo-wide copy slop-gate (grep ban-list, CI) + remaining-routes system adoption | story | S43 |

## Implementation order + what ZCode runs from hallmark

1. **S43 first** — it locks the design system every other page adopts. ZCode
   runs `hallmark study` on the frozen archive + READMEs (extract the DNA),
   then `hallmark redesign` on `/` within the existing Next.js boundary, and
   emits the `design.md`/`tokens.css`.
2. **S44, S45, S46 in parallel after S43** — each is a different macrostructure
   consuming the locked system. ZCode runs `hallmark redesign` per route; each
   PR records the pre-emit six-axis critique and confirms the macrostructure
   differs from the other three (diversification).
3. **S47 after S43** — ZCode runs `hallmark audit` repo-wide to produce the punch
   list; the grep copy-gate lands as CI; the remaining 8 routes adopt the tokens
   (hand-craft deferred to the S47 backlog line).
Parallel lanes: `{S47}` ∥ `{S43 → {S44, S45, S46}}`.

## Rules (apply to every story in this cluster)

- Honesty ladder intact: no fabricated warmth, metric, testimonial, or community
  number; every number keeps its basis. Slop-free copy is not marketing copy.
- The `?as=` contract, middleware, and agent twins (L04 S32/S35) are untouched;
  `llms.txt` is updated in the same cut as any contractual route/copy change.
- Next.js stays; the console stays a static app; zero backend; site copy stays
  English.
- Design gates that cannot be a grep (macrostructure, rhythm, restraint) are a
  **documented hallmark self-critique** the implementer records in the PR (the
  six-axis stamp + the named gates), not a mechanical oracle.
