# Contributing to bestmodel

Thanks for helping build the honest compatibility engine for local AI.

## Ground rules

1. **Number honesty is non-negotiable.** Every displayed number declares its
   basis: `measured > reported > extrapolated > formula > no data yet`.
   An invented number is a critical bug.
2. **Measured data is sacred.** Never weaken assertions in
   `tests/regression/` to make tests pass.
3. Claims and votes never mix into validated leaderboards.

## How to work here

- Every directory has an `AGENTS.md` map; the nearest one to your edit wins.
  Start at the root [`AGENTS.md`](AGENTS.md).
- Specs live in [`specs/en/`](specs/en/) with acceptance commands — make them
  pass before moving on. New stories follow the same format.
- Commits: conventional messages per story (`feat(S13): ...`, `docs: ...`),
  English only.

## Dev setup

```bash
make check-ports && make infra-up
make migrate seed
make test          # single pytest entry
make gate          # end-to-end integration gate
cargo test --workspace   # Rust CLI
```

Requires Docker, Python 3.11+ via [uv](https://docs.astral.sh/uv/), Rust stable.

## Pull requests

- Small, spec-scoped PRs win. If there's no spec, write one first
  (see the L01/L02 format).
- New migrations are append-only files; never edit applied ones.
- Seed ids are deterministic and referenced by tests — add, don't rename.

## License

By contributing you agree your contributions are licensed under
AGPL-3.0 (for `apps/**`) or MIT (for `packages/**` and `cli/**`), matching
the file's scope — see [README licensing section](README.md#license).
