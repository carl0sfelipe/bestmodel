# S47 — Repo-wide copy slop-gate + remaining-routes system adoption

> Decision source: `specs/en/L06-human-craft-web.md` D1/D3. Institutionalizes the
> no-ai-slop copy ban-list as a source-level CI gate over all of web-next, and
> makes the 8 routes outside the human-core four adopt the S43 locked system
> (minimum: drop the slop headlines/words). Full hand-craft of those routes is a
> deferred backlog line.

## Objective

A committed gate script fails CI on any banned copy pattern anywhere in
`apps/web-next/app/**`, and every route references the S43 tokens (no inline
palette), so the site stays coherent and slop-free as it grows.

## Scope

In: `apps/web-next/scripts/slop-gate.sh` (source-level grep gate) wired into CI;
a minimal de-slop sweep of the 8 remaining routes (`/hardware`,
`/track-record`, `/mural`, `/cloud-anchors`, `/submit`, `/profile`, `/m`,
`/claim`) to remove `<br/>` headlines and banned words and adopt tokens.
Out: full hand-craft (macrostructure rework) of those 8 routes — a backlog line;
the human-core four (S43–S46); the console (L04 S34); the agent twins.

## Contract

1. `apps/web-next/scripts/slop-gate.sh`: greps `app/**/*.tsx` and fails (exit 1)
   on any of the L06/S43 ban-list — a `<br` inside an `<h1>`/`<h2>`, the banned
   word list, the binary-contrast shapes, colon-reveal headings, throat-clearing
   openers — printing file:line for each hit. Wired into the existing CI
   (`.github/workflows/`), running on web-next changes.
2. Remaining-routes sweep: the 8 routes drop mid-headline `<br/>` and banned
   words and reference `tokens.css` (no inline hex/OKLCH). Their full
   macrostructure hand-craft is recorded as a backlog line, not done here.
3. `llms.txt` updated if any route/copy contract text changes (L06 D7).

## Rules

Never invent copy to pass the gate — de-slop means removing patterns, not adding
fabricated warmth or metrics (honesty ladder). Never suppress the gate with an
inline ignore to fake a pass (anti-phantom). The analogue of "never use
`declare const` as a workaround": do not comment-out a headline to dodge the
grep instead of rewriting it. The gate greps source, so it must not be defeated by moving
slop into a data file it does not scan — extend the scan instead. Reference S43
tokens by name.
- Gate clause: do not invent a number, metric or copy beyond the ones listed in
  Verified data; missing data renders as "no data yet".
- Gate clause: never use declare const, a stubbed success or a fake badge as a
  workaround — implement the real capability.

## Verified data (2026-09-21)

- Current source ships `<br/>`-split headlines in `app/wall/page.tsx`,
  `app/hardware/page.tsx`, `app/track-record/page.tsx`, `app/console/page.tsx`.
- Tokens are inline in `app/globals.css:2`; S43 introduces `tokens.css`.
- CI workflows live under `.github/workflows/`.

## Acceptance (each criterion = one command)

1. Gate script exists and is executable: `test -x apps/web-next/scripts/slop-gate.sh`
2. Gate passes on the reworked tree: `bash apps/web-next/scripts/slop-gate.sh`
3. The gate actually catches a planted violation (self-test): `printf '<h1>It is a ladder<br/>climbed by acts.</h1>\n' > apps/web-next/app/_slop_probe.tsx; ! bash apps/web-next/scripts/slop-gate.sh; rm -f apps/web-next/app/_slop_probe.tsx`
4. No `<br/>` headline remains anywhere: `! rg -n '<h[12][^>]*>[^<]*<br' apps/web-next/app`
5. No banned words in routes: `! rg -niw 'delve|leverage|utilize|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm|transformative' apps/web-next/app`
6. Gate wired into CI: `rg -q 'slop-gate' .github/workflows/`

## Oráculo

- comando: test -x apps/web-next/scripts/slop-gate.sh && bash apps/web-next/scripts/slop-gate.sh && ! rg -n '<h[12][^>]*>[^<]*<br' apps/web-next/app && ! rg -niw 'delve|leverage|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm|transformative' apps/web-next/app
- exit esperado: 0 — the committed gate passes on a de-slopped tree and no
  `<br/>` headline or banned word remains in any route. Before the sweep the same
  command fails at the `<br/>` scan (the current headlines still ship it) — the
  clean red state.

## Documented hallmark self-critique (implementer fills in the PR)

- The `hallmark audit` punch list for the 8 remaining routes, with the deferred
  hand-craft items listed as the backlog line.
- Confirmation the 8 routes now reference `tokens.css` (no inline palette).

## Dependencies / out of scope

- Depends on: S43 (tokens); complements S44–S46 (their per-route oracles).
- Out: full macrostructure hand-craft of the 8 routes (backlog line), console
  (L04 S34), agent twins, backend.
