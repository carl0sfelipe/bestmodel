//! argos-opt — TPE search engine for the benchmark-probe lab (L03A).
//!
//! # Provenance — READ THIS FIRST
//!
//! **This is a reconstruction, not the original tree.** The original
//! `argos-opt` repository (local git, main at `31feea6`, 3 commits:
//! `0eb65bf` implementation, `3aea764` spec; dual MIT/Apache-2.0;
//! `publish = false`) was lost with the machine it lived on and could not
//! be recovered (search of 2026-09-18: workstation disk at git-object
//! level, full GitHub history of every related repo, the 2026-09-13
//! pre-sale dump of the MacBook that hosted it).
//!
//! On 2026-09-18 the owner authorized vendoring this clean-room
//! reconstruction — written strictly from the public call sites in
//! `cli/benchmark-probe` (tuning_search.rs, lab_recorder.rs,
//! tests/test_tuning_search.rs) — so that a public clone of bestmodel
//! builds. The consumer code compiles UNCHANGED against this crate.
//!
//! **If the original tree resurfaces** (Time Machine snapshot of
//! 2026-08-30/31, the beelink machine): delete this directory, restore
//! the original, and the probe must still compile unchanged. That is the
//! acceptance test for "the real argos-opt is back".
//!
//! # What the crate provides
//!
//! - [`Space`]/[`Dim`]/[`Value`]: the parameter space (continuous,
//!   integer, categorical), with uniform [`Space::sample`].
//! - [`Rng`]: the crate's own PCG32 — seeds fully determine labs.
//! - [`Optimizer`]: ask/tell TPE (minimizes). [`Optimizer::ask`] proposes
//!   the next point, [`Optimizer::tell`] reports
//!   [`TrialResult::Value(loss)`] or [`TrialResult::Failed`],
//!   [`Optimizer::best`] returns the lowest-loss successful trial.
//! - [`TrialLog`]: JSON save/load of the trial history;
//!   [`Optimizer::resume`] rebuilds state from it.
//! - [`Optimizer::run`]: convenience driver loop.
//!
//! Deps are deliberately only `serde`/`serde_json`.

pub mod log;
pub mod rng;
pub mod space;
pub mod tpe;

pub use log::{TrialEntry, TrialLog, TrialResult};
pub use rng::Rng;
pub use space::{params_key, Dim, Space, Value};
pub use tpe::{Optimizer, TpeConfig};
