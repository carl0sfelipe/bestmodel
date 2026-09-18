# argos-opt (vendored reconstruction)

TPE optimizer consumed by `cli/benchmark-probe` (spec L03A).

## Provenance — this is NOT the original tree

- **Original**: local repo at `~/Work/argos-opt`, git `31feea6`
  (ancestors: `3aea764` spec, `0eb65bf` implementation), 3 commits,
  suite 23/23 + sphere demo, deps only serde/serde_json, own PCG32,
  dual MIT/Apache-2.0, `publish = false`. **Lost** with the machine it
  lived on (MacBookPro15,1, later wiped and sold; no remote ever existed).
- **This directory**: clean-room reconstruction of the API surface the
  probe consumes, written 2026-09-18 from the call sites in
  `cli/benchmark-probe` (tuning_search.rs, lab_recorder.rs,
  tests/test_tuning_search.rs), owner-authorized, so a public clone of
  bestmodel builds. It is algorithmically the same family (TPE, ask/tell,
  PCG32, no-repeat, minimizes) but **is not tree `31feea6`**: its measured
  numbers on the L03A stub differ from the ones pinned in the spec
  (406.8 / 329.4 / bar 355.0 were measured with the original crate).
- **Recovery path**: if the original tree resurfaces (Time Machine
  snapshot 2026-08-30/31, or a copy on the beelink machine), replace this
  directory with it — acceptance test: `cargo test -p benchmark-probe`
  green with zero changes outside this directory. Long-term goal stays
  backlog item A11: publish the original as a git/registry dep.

## API (as consumed by the probe — must not drift)

```rust
use argos_opt::{Dim, Optimizer, Space, TpeConfig, TrialResult, Value, Rng};

let space = Space::new(vec![
    Dim::Integer { low: 0, high: 999 },
    Dim::Categorical { choices: vec!["a".into(), "b".into()] },
])?;                                          // Result<Space, String>

let mut opt = Optimizer::new(space.clone(), seed, TpeConfig::default());
for _ in 0..budget {
    let params = opt.ask();                   // Vec<Value>, never repeats
    opt.tell(params, result);                 // TrialResult::Value(loss) | Failed
}
let (best_params, best_loss) = opt.best()?;   // lowest loss wins; failures never do

let p = space.sample(&mut Rng::new(seed));    // uniform draw
```

`Value` serializes externally tagged (`{"Int": 8}`) — the lab's
`index.jsonl`/`best.json` artifacts depend on that shape.

## Layout

- `src/rng.rs` — PCG32 (XSL-RR), Box-Muller normals
- `src/space.rs` — `Dim`, `Value`, `Space`
- `src/tpe.rs` — `TpeConfig`, `Optimizer` (ask/tell TPE)
- `src/log.rs` — `TrialResult`, `TrialLog` (save/load), resume support

## License

Dual MIT OR Apache-2.0 (the owner's 2026-08-30 decision for argos-opt).
See `LICENSE-MIT` and `LICENSE-APACHE`.
