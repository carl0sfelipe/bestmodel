# design.md — the locked system (S43, L06 human-craft pass)

> Source of truth for every visual and copy decision in web-next. Written
> after `hallmark study` over the frozen archive (`apps/web/site/`), the
> owner's README voice, and the L04 surface. Pages **share** this system and
> **differ** in macrostructure — a page that reads as a colour-swap of another
> is a bug (hallmark's core lesson: structural variety, not visual variety).

## Genre

**Editorial-technical.** A terminal-born instrument that reads like a
well-set spec sheet, not an atmospheric dark AI tool. The mono voice carries
the brand (`$ bestmodel.run`, the basis badges, the runbook); display type
carries the human reading. The archive's DNA — the hand-built ecosystem
diagram, the `$` mark, "else: ask — do not guess" — is the soul; the
atmospheric flattening that replaced it was the slop.

## Tokens (`tokens.css`)

Single source for color, type, spacing, motion and radius. Rules reference
tokens by name, never raw values (gate 48). Historical short names (`--bg`,
`--amber`, `--mono`…) are kept verbatim so no shipped rule breaks; new tokens
follow the category prefixes below.

- **color**: `--bg` `--surface` `--surface-2` `--surface-3` `--hair`
  `--hair-strong` `--ink` `--muted` `--dim` `--amber` `--amber-soft`
  `--green` `--red` (+ `--focus`, `--focus-on-accent`)
- **font**: `--mono` (JetBrains Mono — the voice-carrier), `--display`
  (Inter Tight — headings), `--body` (Inter — prose)
- **space**: `--space-1`…`--space-8` (4px scale), `--field-h` (44px touch floor)
- **text**: `--text-xs`/`--text-s`/`--text-m`/`--text-l` mono sizes; display
  sizes stay per-macrostructure (a spec sheet and a workbench do not share a
  hero scale — that is the point)
- **ease/duration**: `--ease-out`, `--ease-in-out`, `--dur-fast/base/slow`
  (reduced-motion always collapses these)
- **radius**: `--radius-s` (6–8px controls), `--radius-m` (12px blocks),
  `--radius-p` (999px pills)

## Palette stance (D5)

The dark terminal base + amber + JetBrains Mono are **brand DNA, kept**. No
repaint unless the system still reads generic after the structural and copy
passes — then a tuned OKLCH pass is an option, not a mandate.

## Macrostructure map (one per route — never shared)

| Route | Macrostructure | Reads as |
|---|---|---|
| `/` | **Workbench** | the intent×rig×quant×context configurator with a live, basis-declaring verdict IS the hero |
| `/cli` | **Long Document / Step Sequence** | a runbook: numbered real steps, real `<pre>` commands, source line to `docs/agent-quickstart.md` |
| `/wall` | **Tabular Spec-Sheet** | the data table is the page; the hero shrinks to a one-line frame with the snapshot date |
| `/claims` | **Feed / Stat-Led** | a stream of claim cards (handle · number+basis · provenance · tally) |
| other 8 | inherited tokens, legacy macrostructure (hand-craft = backlog line) |

## Chrome

- **Masthead (not N1a)**: two mono lines — brand `$ bestmodel.run` + a
  one-line tagline, then an index row of route links. Not the single-row
  wordmark+links fingerprint.
- **Statement footer (not Ft3)**: one editorial line that could only be this
  site (the honesty ladder as a sentence), plus the snapshot caveat. No link
  farm.

## Copy voice (no-ai-slop ban-list — enforced by scripts/slop-gate.sh)

No mid-headline `<br/>`. No binary contrasts ("isn't X. It's Y.",
"not just X but Y"). No colon-reveal headings. No throat-clearing
("here's the thing", "let me be clear"). No grandiloquence or banned words
(delve, leverage, utilize, facilitate, robust, seamless, elevate, embark,
supercharge, harness, unlock, realm, tapestry, paradigm, game-changer,
cutting-edge, ever-evolving, transformative). Headings are roman (no italic
display). Numbers keep their basis label — slop-free copy is not warmer
marketing; over-sweetening past the data is the same sin inverted.

## Honesty rules that outrank taste

The honesty ladder (measured > reported > extrapolated > formula > no data
yet) renders as structure: a spec sheet for the pool, a runbook for the CLI,
a live basis-declaring workbench for home. No invented node, metric, handle
or testimonial. A cell without a source class never renders.
