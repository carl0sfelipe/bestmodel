//! L03A integration tests — one per mandatory behavior in
//! specs/en/L03A-tpe-lab-search.md.

use std::fs;
use std::path::PathBuf;
use std::process::Command;

use benchmark_probe::tuning_search::{run_lab, stub_objective, LabSpace};
use argos_opt::{Rng, Value};

fn tmp_root(tag: &str) -> PathBuf {
    let p = std::env::temp_dir().join(format!("bm-l03a-{}-{}", tag, std::process::id()));
    fs::remove_dir_all(&p).ok();
    fs::create_dir_all(&p).unwrap();
    p
}

fn random_objective_baseline(trials: usize, seed: u64, space: &LabSpace) -> f64 {
    // uniform-random baseline over the same space, same budget
    let mut rng = Rng::new(seed);
    let mut best = f64::NEG_INFINITY;
    for _ in 0..trials {
        let p = space.space().sample(&mut rng);
        if let Ok(v) = stub_objective(&p) {
            if v > best {
                best = v;
            }
        }
    }
    best
}

/// Behavior 2 (OOM) + Behavior 5 (recorder) through the real loop.
/// The failure is INJECTED (wide deterministic rule: ngl > 900 OOMs) —
/// the mechanism under test is "failed trial -> null -> never wins", not
/// the seed luck of landing in the stub's narrow OOM corner (that corner
/// itself is pinned by the stub unit test).
#[test]
fn oom_lands_as_null_and_never_wins() {
    let root = tmp_root("oom");
    let space = LabSpace::new().unwrap();
    let mut objective = |p: &Vec<Value>| {
        let oom = matches!(&p[0], Value::Int(ngl) if *ngl > 900);
        if oom { Err(()) } else { stub_objective(p) }
    };
    let out = run_lab(&space, 30, 42, &mut objective, &root, "oom-lab").unwrap();

    let index = fs::read_to_string(out.lab_dir.join("index.jsonl")).unwrap();
    let lines: Vec<serde_json::Value> =
        index.lines().map(|l| serde_json::from_str(l).unwrap()).collect();
    assert_eq!(lines.len(), 30);
    let nulls = lines.iter().filter(|l| l["value"].is_null()).count();
    assert!(nulls > 0, "injected OOM region must produce failed trials");
    // best is never a failed trial and never sits in the OOM region
    let best: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(out.lab_dir.join("best.json")).unwrap()).unwrap();
    assert!(best["value"].as_f64().unwrap() > 0.0);
    assert!(best["server_command"].as_str().unwrap().starts_with("llama-server"));
    assert!(best["params"][0]["Int"].as_i64().unwrap() <= 900);
    fs::remove_dir_all(&root).ok();
}

/// Behavior 1 (determinism): same seed -> same best + identical index.
#[test]
fn same_seed_same_lab() {
    let root = tmp_root("det");
    let space = LabSpace::new().unwrap();
    let mut o1 = |p: &Vec<Value>| stub_objective(p);
    let mut o2 = |p: &Vec<Value>| stub_objective(p);
    let a = run_lab(&space, 40, 42, &mut o1, &root, "run-a").unwrap();
    let b = run_lab(&space, 40, 42, &mut o2, &root, "run-b").unwrap();
    assert_eq!(a.best_params, b.best_params);
    assert_eq!(a.best_value, b.best_value);
    let ia = fs::read_to_string(a.lab_dir.join("index.jsonl")).unwrap();
    let ib = fs::read_to_string(b.lab_dir.join("index.jsonl")).unwrap();
    assert_eq!(ia, ib);
    fs::remove_dir_all(&root).ok();
}

/// Behavior 3 (intelligent beats brute — the owner's constraint) and
/// Behavior 4 (no repeats), measured and pinned per the spec.
///
/// MEASURED 2026-08-30, seed 42, 60 trials on the stub:
///   TPE best     = 406.8 tok/s
///   random best  = 329.4 tok/s
/// Bar = midpoint (355.0): TPE >= bar, random < bar. Adjust ONLY with a
/// re-measurement recorded in the spec — never to let a cut pass.
#[test]
fn tpe_beats_random_baseline() {
    const BAR: f64 = 355.0;
    let space = LabSpace::new().unwrap();
    let root = tmp_root("ab");

    let mut objective = |p: &Vec<Value>| stub_objective(p);
    let out = run_lab(&space, 60, 42, &mut objective, &root, "ab-lab").unwrap();
    assert!(
        out.best_value >= BAR,
        "TPE must reach the measured bar: {} < {BAR}",
        out.best_value
    );
    let random_best = random_objective_baseline(60, 42, &space);
    assert!(
        random_best < BAR,
        "random baseline must stay below the bar: {random_best} >= {BAR}"
    );
    assert!(out.best_value > random_best);
    // keep the measured numbers visible: pinned bar must track reality
    println!("MEASURED seed42/60: tpe={} random={} bar={BAR}", out.best_value, random_best);

    // Behavior 4: TPE never evaluated the same params twice.
    let index = fs::read_to_string(out.lab_dir.join("index.jsonl")).unwrap();
    let mut seen = std::collections::HashSet::new();
    for l in index.lines() {
        let v: serde_json::Value = serde_json::from_str(l).unwrap();
        assert!(seen.insert(v["params"].to_string()), "repeat evaluated: {v}");
    }
    fs::remove_dir_all(&root).ok();
}

/// Behavior 7: the real binary, `lab --stub --trials 20 --json` end to end.
#[test]
fn cli_lab_stub_smoke() {
    let root = tmp_root("cli");
    let bin = env!("CARGO_BIN_EXE_benchmark-probe");
    let out = Command::new(bin)
        .args(["lab", "--stub", "--trials", "20", "--out"])
        .arg(&root)
        .output()
        .expect("binary runs");
    assert!(out.status.success(), "stderr: {}", String::from_utf8_lossy(&out.stderr));
    let stdout = String::from_utf8_lossy(&out.stdout);
    assert!(stdout.contains("SIM"), "stub output must be SIM-marked: {stdout}");
    assert!(stdout.contains("llama-server"));

    // --json prints exactly the best.json content OF THE NEW LAB
    let before: std::collections::HashSet<PathBuf> =
        fs::read_dir(&root).unwrap().map(|e| e.unwrap().path()).collect();
    let out_json = Command::new(bin)
        .args(["lab", "--stub", "--trials", "5", "--out"])
        .arg(&root)
        .arg("--json")
        .output()
        .expect("binary runs");
    assert!(out_json.status.success(), "stderr: {}", String::from_utf8_lossy(&out_json.stderr));
    let printed = String::from_utf8_lossy(&out_json.stdout);
    let new_dir: Vec<_> = fs::read_dir(&root)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| !before.contains(p))
        .collect();
    assert_eq!(new_dir.len(), 1);
    let on_disk = fs::read_to_string(new_dir[0].join("best.json")).unwrap();
    assert_eq!(printed.trim_end(), on_disk.trim_end());

    // missing --stub refuses (real objective does not exist yet)
    let refused = Command::new(bin).args(["lab"]).output().unwrap();
    assert_eq!(refused.status.code(), Some(2));

    fs::remove_dir_all(&root).ok();
}
