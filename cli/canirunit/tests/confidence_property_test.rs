//! Property-style tests for the Story 2.3 confidence function (AD-5):
//! deterministic sweeps via the in-crate LCG — no external quickcheck.

use canirunit::confidence::{confidence, ConfidenceInputs, MatchTier, Lcg, SOURCE_WEIGHT_ORDER};

fn inputs(source_class: &str, n_runs: usize, age_days: f64, variance: f64, mean: f64, tier: MatchTier) -> ConfidenceInputs {
    ConfidenceInputs {
        source_class: source_class.to_string(),
        n_runs,
        age_days,
        variance,
        mean,
        match_tier: tier,
    }
}

#[test]
fn monotone_non_decreasing_in_n_runs() {
    let mut rng = Lcg::new(42);
    for _ in 0..200 {
        let class = ["measured_signed", "reported", "harvested"][(&rng.next_u64() % 3) as usize];
        let age = rng.next_f64(365.0);
        let mean = 1.0 + rng.next_f64(200.0);
        let variance = rng.next_f64(mean * 0.4);
        let mut previous = 0.0_f64;
        for n in 1..=12 {
            let value = confidence(&inputs(class, n, age, variance, mean, MatchTier::Exact));
            assert!(
                value >= previous - 1e-9,
                "confidence decreased with more runs: n={n} {previous} -> {value} ({class})"
            );
            previous = value;
        }
    }
}

#[test]
fn monotone_non_increasing_in_variance() {
    let mut rng = Lcg::new(7);
    for _ in 0..200 {
        let mean = 10.0 + rng.next_f64(190.0);
        let age = rng.next_f64(365.0);
        let mut previous = confidence(&inputs("measured_signed", 3, age, 0.0, mean, MatchTier::Exact));
        for step in 1..=10 {
            let variance = mean * 0.06 * step as f64;
            let value = confidence(&inputs("measured_signed", 3, age, variance, mean, MatchTier::Exact));
            assert!(
                value <= previous + 1e-9,
                "confidence increased with variance: {variance} {previous} -> {value}"
            );
            previous = value;
        }
    }
}

#[test]
fn monotone_non_increasing_in_age() {
    let mut rng = Lcg::new(99);
    for _ in 0..200 {
        let mean = 1.0 + rng.next_f64(100.0);
        let variance = rng.next_f64(mean * 0.3);
        let mut previous = confidence(&inputs("reported", 2, 0.0, variance, mean, MatchTier::Exact));
        for step in 1..=10 {
            let age = 90.0 * step as f64;
            let value = confidence(&inputs("reported", 2, age, variance, mean, MatchTier::Exact));
            assert!(
                value <= previous + 1e-9,
                "confidence increased with age: {age} {previous} -> {value}"
            );
            previous = value;
        }
    }
}

#[test]
fn bounded_between_zero_and_one() {
    let mut rng = Lcg::new(1);
    for _ in 0..1000 {
        let value = confidence(&inputs(
            "measured_signed",
            1 + (&rng.next_u64() % 20) as usize,
            rng.next_f64(3000.0),
            rng.next_f64(500.0),
            rng.next_f64(500.0),
            MatchTier::Exact,
        ));
        assert!((0.0..=1.0).contains(&value), "out of bounds: {value}");
    }
}

#[test]
fn exact_ge_family_ge_roofline() {
    let mut rng = Lcg::new(5);
    for _ in 0..300 {
        let n = 1 + (&rng.next_u64() % 10) as usize;
        let age = rng.next_f64(365.0);
        let mean = 1.0 + rng.next_f64(100.0);
        let variance = rng.next_f64(mean * 0.5);
        let exact = confidence(&inputs("measured_signed", n, age, variance, mean, MatchTier::Exact));
        let family = confidence(&inputs("measured_signed", n, age, variance, mean, MatchTier::SameFamily));
        let roofline = confidence(&inputs("measured_signed", n, age, variance, mean, MatchTier::Roofline));
        assert!(exact >= family - 1e-9 && family >= roofline - 1e-9);
    }
}

#[test]
fn class_order_measured_over_reported_over_harvested() {
    let base_input = |class: &str| inputs(class, 5, 30.0, 2.0, 100.0, MatchTier::Exact);
    let measured = confidence(&base_input("measured_signed"));
    let reported = confidence(&base_input("reported"));
    let harvested = confidence(&base_input("harvested"));
    let unknown = confidence(&base_input("who-knows"));
    assert!(measured > reported && reported > harvested && harvested > unknown);
    assert_eq!(SOURCE_WEIGHT_ORDER, ["measured_signed", "reported", "harvested", "derived"]);
}
