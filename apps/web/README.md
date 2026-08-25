# apps/web — the bestmodel.run static site

The public-facing compatibility engine at [bestmodel.run](https://bestmodel.run):
vanilla HTML/CSS/JS (zero frameworks, zero npm deps), fed by a frozen data
snapshot derived from the community measurement pool.

## Layout

| Path | Content |
|---|---|
| `site/` | Deployable static site (index, hardware journey, mobile landing, SEO pages) |
| `console/` | Interactive web console (S19): passkey sign-in, feed, vote, claim, settle command — vanilla JS over the public API; API base via `window.BESTMODEL_API` |
| `data/derived/` | Frozen JSON snapshot consumed by the site (`models`, `hardware`, `pool`, `stats`) |
| `data/seed/` | Verified bandwidth seed values |
| `prototypes/` | Final visual spec (do not edit): goal-first, hardware-first, mobile |
| `scripts/` | Data pipeline: `harvest.mjs` → `derive.mjs` → `gen-seo.mjs`; `check.mjs` is the oracle |
| `specs/` | Build sessions S1–S8 (historical, in Portuguese) |
| `tests/` | Pipeline tests (node:test) |

## Non-negotiable principle: number honesty

Every displayed number carries a declared basis, in strict order:

`measured` (pool median) > `reported` (1–2 runs) > `extrapolated`
(bandwidth-scaled) > **no data yet** (rendered honestly).

An invented number is a critical bug.

## Rebuild the data snapshot

Console oracle (structure + every API touchpoint of the no-terminal loop):

```bash
node scripts/check-console.mjs
```

Data pipeline:

```bash
cd apps/web
node scripts/harvest.mjs   # pull community pool → data/raw
node scripts/derive.mjs    # aggregate → data/derived
node scripts/gen-seo.mjs   # regenerate site/p/ pages + sitemap
node scripts/check.mjs all # full oracle
```

Requires Node >= 22 and `jq`. The site itself never calls an API at runtime —
it ships as a self-contained snapshot by design.
