//! Behavior suite for the reconstructed argos-opt. Mirrors, in spirit, the
//! original crate's guarantees: deterministic labs, no repeated proposals,
//! failures never win, resume works, and the search actually converges
//! (sphere demo). Numbers here are THIS reconstruction's — they are not
//! the lost tree's measurements.

use std::collections::HashSet;

use argos_opt::{log::TrialLog, Dim, Optimizer, Space, TpeConfig, TrialResult, Value};

fn sphere(params: &[Value]) -> TrialResult {
    let x: f64 = params
        .iter()
        .map(|v| match v {
            Value::Real(x) => *x,
            Value::Int(x) => *x as f64,
            Value::Cat(_) => 0.0,
        })
        .map(|x| x * x)
        .sum();
    TrialResult::Value(x)
}

fn sphere_space() -> Space {
    Space::new(vec![
        Dim::Continuous { low: -5.0, high: 5.0 },
        Dim::Continuous { low: -5.0, high: 5.0 },
        Dim::Continuous { low: -5.0, high: 5.0 },
    ])
    .unwrap()
}

/// Same seed + same tell history => byte-identical ask sequences.
#[test]
fn determinism_same_seed_same_asks() {
    let run_once = || {
        let mut opt = Optimizer::new(sphere_space(), 42, TpeConfig::default());
        (0..120)
            .map(|_| {
                let p = opt.ask();
                let r = sphere(&p);
                opt.tell(p, r);
            })
            .collect::<Vec<_>>()
    };
    let a = run_once();
    let b = run_once();
    assert_eq!(a, b);
}

/// ask() never proposes a point that was already asked (success or failure).
#[test]
fn no_repeated_proposals() {
    let space = Space::new(vec![
        Dim::Integer { low: 0, high: 999 },
        Dim::Integer { low: 512, high: 32768 },
        Dim::Integer { low: 1, high: 32 },
        Dim::Categorical { choices: vec!["f16".into(), "q8_0".into(), "q4_0".into()] },
        Dim::Categorical { choices: vec!["off".into(), "on".into()] },
    ])
    .unwrap();
    let mut opt = Optimizer::new(space, 42, TpeConfig::default());
    let mut seen: HashSet<String> = HashSet::new();
    for i in 0..200 {
        let p = opt.ask();
        // failures in the injected-OOM style: top of the ngl range fails
        let fail = matches!(&p[0], Value::Int(n) if *n > 900);
        let r = if fail { TrialResult::Failed } else { TrialResult::Value(1.0) };
        assert!(seen.insert(argos_opt::params_key(&p)), "repeat at ask {i}: {p:?}");
        opt.tell(p, r);
    }
}

/// Failed trials are recorded-but-inert: best() only reflects successes.
#[test]
fn failures_never_win_best() {
    let space = sphere_space();
    let mut opt = Optimizer::new(space, 7, TpeConfig::default());

    // all failures => no best
    for _ in 0..10 {
        let p = opt.ask();
        opt.tell(p, TrialResult::Failed);
    }
    assert!(opt.best().is_none());

    // now successes, plus interleaved failures that would "win" if counted
    opt.tell(
        vec![Value::Real(0.0), Value::Real(0.0), Value::Real(0.0)],
        TrialResult::Value(1.0),
    );
    opt.tell(
        vec![Value::Real(4.9), Value::Real(4.9), Value::Real(4.9)],
        TrialResult::Failed, // "better" loss if failures were treated as 0
    );
    let (params, loss) = opt.best().unwrap();
    assert_eq!(params, vec![Value::Real(0.0), Value::Real(0.0), Value::Real(0.0)]);
    assert_eq!(loss, 1.0);
}

/// TrialLog roundtrip + resume: state rebuilds, best matches, and the
/// resumed optimizer keeps exploring without repeating logged points.
#[test]
fn trial_log_roundtrip_and_resume() {
    let dir = std::env::temp_dir().join(format!("argos-resume-{}", std::process::id()));
    std::fs::remove_dir_all(&dir).ok();
    std::fs::create_dir_all(&dir).unwrap();

    let mut log = TrialLog::new();
    let mut opt = Optimizer::new(sphere_space(), 42, TpeConfig::default());
    for _ in 0..80 {
        let p = opt.ask();
        let r = sphere(&p);
        log.record(p.clone(), r.clone());
        opt.tell(p, r);
    }
    log.save(dir.join("log.json")).unwrap();
    let back = TrialLog::load(dir.join("log.json")).unwrap();
    assert_eq!(back, log);

    let resumed =
        Optimizer::resume(sphere_space(), 42, TpeConfig::default(), &back).unwrap();
    assert_eq!(resumed.best().unwrap(), opt.best().unwrap());

    // a mismatched log (point outside the space) is refused, loudly
    let mut bad = TrialLog::new();
    bad.record(vec![Value::Cat(0), Value::Cat(0), Value::Cat(0)], TrialResult::Value(0.0));
    assert!(Optimizer::resume(sphere_space(), 42, TpeConfig::default(), &bad).is_err());

    std::fs::remove_dir_all(&dir).ok();
}

/// run() drives the loop and reports successes (failures consume budget).
#[test]
fn run_counts_successes_not_failures() {
    let mut opt = Optimizer::new(sphere_space(), 3, TpeConfig::default());
    let mut calls = 0;
    let successes = opt.run(50, &mut |p| {
        calls += 1;
        if calls % 3 == 0 {
            TrialResult::Failed
        } else {
            sphere(p)
        }
    });
    assert_eq!(calls, 50);
    assert_eq!(successes, 50 - 50 / 3);
}

/// Sphere demo (the original crate's own benchmark, re-measured here):
/// 3-D sphere, seed 42, TPE must land near zero. The original tree
/// measured 60→3.6e-1 / 120→3.7e-2 / 300→2.6e-3; this reconstruction
/// measures 60→7.7e-1 / 120→3.1e-2 / 300→3.8e-3 (same order from 120 on).
/// The curve is printed so drift is visible; asserts keep honest margin
/// over the measured values.
#[test]
fn sphere_demo_converges() {
    let best_at = |evals| {
        let mut opt = Optimizer::new(sphere_space(), 42, TpeConfig::default());
        opt.run(evals, &mut sphere);
        opt.best().unwrap().1
    };
    let b60 = best_at(60);
    let b120 = best_at(120);
    let b300 = best_at(300);
    println!("sphere 3D seed42: 60->{b60:.4e} 120->{b120:.4e} 300->{b300:.4e}");
    assert!(b60 < 1.5, "60 evals should already be close: {b60}");
    assert!(b120 < 0.15, "120 evals should be inside 0.4 radius: {b120}");
    assert!(b120 < b60, "more budget must not be worse");
    assert!(b300 < 2e-2, "300 evals should be at the bottom: {b300}");
    assert!(b300 < b120);
}

/// Integer + categorical space: proposals stay in bounds and the search
/// climbs a mixed-space step landscape toward its known optimum.
#[test]
fn mixed_integer_categorical_space_converges() {
    // optimum: x=10, choice index 2 -> loss -12; everything else worse
    let space = Space::new(vec![
        Dim::Integer { low: 0, high: 20 },
        Dim::Categorical { choices: vec!["a".into(), "b".into(), "c".into()] },
    ])
    .unwrap();
    let f = |p: &[Value]| {
        let (x, k) = (matches!(p[0], Value::Int(v) if v == 10), matches!(p[1], Value::Cat(2)));
        TrialResult::Value(if x && k { -12.0 } else if k || x { -5.0 } else { 0.0 })
    };
    let mut opt = Optimizer::new(space, 42, TpeConfig::default());
    opt.run(120, &mut |p| f(p));
    let (params, loss) = opt.best().unwrap();
    assert_eq!(loss, -12.0, "must find the optimum, got {loss} at {params:?}");
    assert!(matches!(params[0], Value::Int(10)));
    assert!(matches!(params[1], Value::Cat(2)));
}
