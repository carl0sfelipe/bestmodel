# L07 — Native leave-running audio bench (community)

> Source: 2026-09-23 dogfood on a real RTX 3090. Workbench `Audio ×
> rtx-3090-24gb` was empty. The only way to get a Portuguese number was a
> side script (faster-whisper + FLEURS), not `benchmark-probe`. This epic
> is the cut list so a later agent can build the path a stranger would
> actually leave running overnight — and so the pool gets better because
> people compete on **missing holes**, not vanity ×real.

This file is the epic. Stories are **not opened**. Do not implement from
chat. The first public cell that this gap forced is
`docs/measurements/2026-09-23-audio-pt-br-3090.md`.

## Why the side script is not the product

- `benchmark-probe` has no audio runtime. `plan` ranks `decode_tok_s`.
- `canirunit suggest --task seconds_per_clip` is **video** wall time
  (lower is better). Teaching it to swallow ASR RTF would mix units.
- Contract 0.9.0 stores `audioXReal`. It has no `wer`, no `language`,
  no `recipeId`. Speed without language is how the L4 4.82×real cell
  almost became a fake Portuguese answer.
- Clip-level dumps do not belong in git. The 919-row WER json is large
  data; the public tree keeps the three speed rows + one WER summary.

## Decision record

Size: **story** (open later) · **line** · **rejection**.

### D1 — Recipe is the unit — **story (later)**

One JSON recipe: dataset + split + language + engine + weights +
decode knobs (beam, VAD, compute type). Two runs with the same
`recipeId` are comparable. Two runs that only share a model slug are not.

Rejected: a notebook in `docs/` as the long-term runner. The 2026-09-23
script was an incident response, not a surface.

### D2 — Two metrics, both required to *rank* quality — **story (later)**

- `audioXReal` — already on the workbench (higher is better).
- `wer` (or CER) **plus** `language` — not in the contract today.
  Until that field exists, WER lives on a measurement card and stays
  labeled `reported` until n≥3.

Rejected: putting WER into `audioXReal` or into `seconds_per_clip`.
Rejected: ranking Portuguese from an unlabeled speed cell.

### D3 — Leave-running is the default loop — **story (later)**

`benchmark-probe audio --recipe R --until done|12h` writes an immutable
run directory, repeats until n≥3 or the clock ends, and
`contribute`s the best cell (A3 opt-out, already closed). A person
starts it and walks away. SIM/stub cells stay refused (S41).

Rejected: interactive one-clip demos as the community path.

### D4 — Gamify empty holes, not leaderboard theatre — **line (A3)**

A3 already pays points for signed shares (llms.surf giveaway lists,
per product). Audio should score **coverage**: `(rig × language ×
recipe)` that the pool lacks beats a 0.3× gain on a cell that exists.
Society-facing optimization = fill the map, then tighten WER on the
same recipe.

Rejected: a second points system. Reuse A3.

### D5 — Blobs stay off the public tree — **line**

Summary + ingest.jsonl in-repo. Wavs, Hub weights, and per-clip hyp/ref
stay outside git (same rule as ORG-L7 for large data). A later agent
reproduces from the recipe + the official dataset URL.

### D6 — New canirunit task `audio_xreal` — **story (later)**

Higher is better. Corpus rows need `audio_xreal` (or the pool cell's
`audioXReal` mapped at harvest). Exit 3 remains the honest empty.

Rejected: aliasing `seconds_per_clip` to ASR. That metric is video
and **lower** is better.

### D7 — Measure published weights — **rejection (YAGNI here)**

Fine-tunes (Qwen3-ASR-1.7B-PT, etc.) are candidates **after** the
recipe runner exists. This epic does not train. Do not quote another
vendor's unnamed-GPU RTF as a 3090 number (see the 2026-09-23 card).

### D8 — First recipe is the one already run — **line**

`faster-whisper` + FLEURS `{lang}` test + `language=` + VAD + beam 5 +
`float16`. That is the seed recipe a stranger can clone. Whisper
`large-v3` / `medium` and Qwen3-ASR 0.6B/1.7B are the next recipes,
not a new epic.

## Cut list (open as stories only when implementing)

| Later id (suggested) | Delivers | Oracle sketch |
|---|---|---|
| S48 | optional `wer`, `language`, `recipeId` on audio cells | schema test: cell without them still loads; cell with them ranks quality only among the same recipe+language |
| S49 | `benchmark-probe` audio runtime (one engine first: faster-whisper) | `--recipe` dry-run prints plan; stub is SIM; real run writes ingest.jsonl |
| S50 | `--until` leave-running + contribute of n≥3 | three reps on a tiny fixture; SIM refused |
| S51 | `canirunit suggest --task audio_xreal` | exit 3 on empty; ranks the 3090 turbo cell from this repo's pool |
| S52 | workbench shows language + WER when present, speed always | Audio × 3090 no longer "no data" after S48+cell (speed already lands from the 2026-09-23 append) |

Order: S48 (contract) → S49 (probe) → S50 (loop) → S51 (query) → S52
(view). S52 can ship a speed-only badge before S48 if the cell exists
(this PR).

## What a cold agent must not do

- Fill `NotImplementedError` in the probe by pasting the 2026-09-23
  side script into `cli/benchmark-probe` without a story.
- Commit FLEURS wavs or 919-row hyp/ref dumps.
- Copy executor contracts, handoffs, or incident files back into this
  tree (L03 withdraw, 592af53).
- Answer "best Portuguese ASR" from `l4-24gb` 4.82×real.

## Pointers

- Measurement that closed the empty speed cell: `docs/measurements/2026-09-23-audio-pt-br-3090.md`
- Honesty ladder: `docs/agent-quickstart.md`
- Contribute / A3: `docs/contribute.md`, backlog A3
- Pool the workbench reads: `apps/web-next/public/data/derived/pool.json`
