//! PCG32 — the crate's own deterministic random generator.
//!
//! Standard PCG-XSL-RR 32-bit output over a 64-bit LCG state
//! (O'Neill, "PCG: A Family of Simple Fast Space-Efficient Statistically
//! Good Algorithms for Random Number Generation"). No dependency on rand:
//! the whole point is that a seed fully determines the lab.

/// Deterministic PCG32 generator. Same seed + same call sequence => same
/// numbers, forever, on every platform (no clock, no thread state).
#[derive(Clone, Debug)]
pub struct Rng {
    state: u64,
    inc: u64,
    spare_normal: Option<f64>,
}

const MULTIPLIER: u64 = 6364136223846793005;
/// Arbitrary fixed odd stream selector. The value itself carries no
/// meaning; it is pinned so results are reproducible across builds.
const DEFAULT_STREAM: u64 = 0xda3e_39cb_94b9_5bdb;

impl Rng {
    /// Seeded generator on the default (fixed) stream.
    pub fn new(seed: u64) -> Rng {
        Rng::with_stream(seed, DEFAULT_STREAM)
    }

    /// Seeded generator on a caller-chosen stream (the low bit is forced
    /// to 1, as PCG requires an odd increment).
    pub fn with_stream(seed: u64, stream: u64) -> Rng {
        let mut rng = Rng {
            state: 0,
            inc: (stream << 1) | 1,
            spare_normal: None,
        };
        rng.next_u32(); // scramble the zero state
        rng.state = rng.state.wrapping_add(seed);
        rng.next_u32();
        rng
    }

    /// Raw 32 random bits.
    pub fn next_u32(&mut self) -> u32 {
        let old = self.state;
        self.state = old
            .wrapping_mul(MULTIPLIER)
            .wrapping_add(self.inc);
        // XSL-RR: xorshift-high then rotate right by the top 5 bits of old
        let xorshifted = (((old >> 18) ^ old) >> 27) as u32;
        let rot = (old >> 59) as u32;
        xorshifted.rotate_right(rot)
    }

    /// Uniform f64 in [0, 1). 2^-32 granularity is plenty for search.
    pub fn next_f64(&mut self) -> f64 {
        (self.next_u32() as f64) * (1.0 / 4294967296.0)
    }

    /// Uniform f64 in [lo, hi).
    pub fn next_range(&mut self, lo: f64, hi: f64) -> f64 {
        lo + self.next_f64() * (hi - lo)
    }

    /// Uniform integer in [0, n) — multiply-shift (Lemire), unbiased.
    pub fn below(&mut self, n: u64) -> u64 {
        ((self.next_u32() as u64) * n) >> 32
    }

    /// Standard normal via Box-Muller (the second variate is cached).
    pub fn normal(&mut self) -> f64 {
        if let Some(z) = self.spare_normal.take() {
            return z;
        }
        // u1 in (0, 1]: log(0) must not happen
        let u1 = 1.0 - self.next_f64();
        let u2 = self.next_f64();
        let r = (-2.0 * u1.ln()).sqrt();
        let theta = 2.0 * std::f64::consts::PI * u2;
        self.spare_normal = Some(r * theta.sin());
        r * theta.cos()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_seed_same_sequence() {
        let mut a = Rng::new(42);
        let mut b = Rng::new(42);
        for _ in 0..1000 {
            assert_eq!(a.next_u32(), b.next_u32());
        }
    }

    #[test]
    fn different_seeds_diverge() {
        let mut a = Rng::new(1);
        let mut b = Rng::new(2);
        assert_ne!(a.next_u32(), b.next_u32());
    }

    #[test]
    fn below_stays_in_range() {
        let mut rng = Rng::new(7);
        for n in 1..100u64 {
            for _ in 0..50 {
                assert!(rng.below(n) < n);
            }
        }
    }

    #[test]
    fn normal_is_finite_and_centered_enough() {
        let mut rng = Rng::new(9);
        let mut sum = 0.0;
        let n = 20000;
        for _ in 0..n {
            let z = rng.normal();
            assert!(z.is_finite());
            sum += z;
        }
        let mean = sum / n as f64;
        assert!(mean.abs() < 0.05, "mean drifted: {mean}");
    }
}
