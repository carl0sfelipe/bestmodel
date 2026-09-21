# S44 — `/cli` human-craft (Long Document / Step Sequence)

> Decision source: `specs/en/L06-human-craft-web.md` D2/D3/D8. Hand-crafts the
> human view of `/cli` as a runbook document — real commands, no marketing hero —
> on the locked system from S43. Keeps the L04 S33 honesty (only shipped
> subcommands) and the strings its oracle greps.

## Objective

`/cli` reads as a document a human follows to install and run the CLI:
build → `benchmark-probe` → `lab`, with `plan`/`report`/`contribute` shown only
as a labelled "not shipped yet" block. Commands render in real `<pre>` blocks
(no fake terminal chrome), copy is slop-free, and the page is structurally
distinct from home.

## Scope

In: the `/cli` human view (`apps/web-next/app/cli/`), Long Document / Step
Sequence macrostructure on the S43 tokens; de-slop copy; real code blocks.
Out: the L04 S33 route wiring itself, nav entry, phantom-installer removal, and
`llms.txt` (owned by S33 — this story is the human-craft layer on top); the
agent twin; backend.

## Contract

1. Macrostructure = **Long Document / Step Sequence**: numbered real steps, not
   a `page-head` hero + card grid. Retire the `.kicker` + `<br/>` headline.
2. Code blocks are real `<pre>`/`<code>` with at most a hairline border — no
   hand-built browser bar, traffic-light dots, or fake terminal window (hallmark
   gate 47).
3. Keep the literal honest strings the L04 S33 oracle greps: `benchmark-probe`
   and `agent-smoke` appear in the human copy (they are the real commands);
   `plan`/`report`/`contribute` stay inside a visible "not shipped yet" block.
4. Copy passes the L06/S43 ban-list; headings roman, no mid-headline `<br/>`.

## Rules

Never document or invoke a subcommand the binary does not dispatch in the same
commit (honesty ladder / anti-phantom). The analogue of "never use
`declare const` as a workaround": do not render a not-shipped command as
runnable.
Never invent a number or an install one-liner. Reference S43 tokens by name; do
not inline raw values. Do not touch the `?as=` twin or weaken L04 S33's oracle.

## Verified data (2026-09-21)

- Only `lab` dispatches today (`cli/benchmark-probe/src/main.rs`);
  `plan`/`report`/`contribute` are planned (L05 S39/S40/S41).
- `docs/agent-quickstart.md` is the verified source `/cli` renders (L04 S33).
- L04 S33 c2 greps `/cli` for `benchmark-probe` and `agent-smoke`.

## Acceptance (each criterion = one command)

App up: `cd apps/web-next && pnpm install && pnpm build && pnpm start &`
(`U=http://localhost:3000`).

1. `/cli` serves a human view: `curl -s "$U/cli?as=human" | grep -q 'data-view="human"'`
2. L04 S33 strings preserved: `curl -s "$U/cli" | grep -q 'benchmark-probe' && curl -s "$U/cli" | grep -q 'agent-smoke'`
3. Unshipped subcommands quarantined: `curl -s "$U/cli" | grep -iq 'not shipped'`
4. No mid-headline break: `! curl -s "$U/cli" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br'`
5. No banned words / binary contrast: `! curl -s "$U/cli" | grep -Eiwq 'delve|leverage|robust|seamless|elevate|supercharge|harness|unlock|realm|tapestry|paradigm' && ! curl -s "$U/cli" | grep -Eiq "isn't .+ it's|not just .+ but"`
6. Real code block, no fake chrome: `curl -s "$U/cli" | grep -q '<pre' && ! curl -s "$U/cli" | grep -Eiq 'traffic-light|window-dots|fake-terminal'`

## Oráculo

- comando: cd apps/web-next && pnpm install && pnpm build && pnpm start & sleep 8; U=http://localhost:3000; curl -s "$U/cli?as=human" | grep -q 'data-view="human"' && curl -s "$U/cli" | grep -q 'benchmark-probe' && curl -s "$U/cli" | grep -q 'agent-smoke' && curl -s "$U/cli" | grep -iq 'not shipped' && ! (curl -s "$U/cli" | tr '\n' ' ' | grep -Eiq '<h[12][^>]*>[^<]*<br')
- exit esperado: 0 — `/cli` reads as a runbook with real commands, honest
  quarantine, and no slop headline. Before the human-craft rework the same
  command fails at the `<br/>` check (the shared `page-head` pattern) — the clean
  red state.

## Documented hallmark self-critique (implementer fills in the PR)

- Pre-emit six-axis score (each ≥ 3) from the CSS stamp.
- Gates absent: 38a, 46, 47 (code chrome is the key one here), 48, 54; responsive
  320/375/414/768.
- Diversification: Long Document differs from home Workbench and from S45/S46.

## Dependencies / out of scope

- Depends on: L04 S33 (the `/cli` route + source) and S43 (tokens).
- Out: S33's wiring/`llms.txt`, the agent twin, backend.
