//! Search space: dimensions and parameter values.

use serde::{Deserialize, Serialize};

use crate::rng::Rng;

/// One dimension of the search space.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum Dim {
    Continuous {
        low: f64,
        high: f64,
    },
    Integer {
        low: i64,
        high: i64,
    },
    Categorical {
        choices: Vec<String>,
    },
}

/// A concrete parameter value. Serialized externally tagged (`{"Int": 8}`),
/// which is the on-disk shape the benchmark-probe lab artifacts rely on.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum Value {
    Int(i64),
    Real(f64),
    Cat(usize),
}

/// A validated set of dimensions.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Space {
    dims: Vec<Dim>,
}

impl Space {
    /// Validates and builds a space. Errors (as plain strings — this is a
    /// CLI-facing crate) on: empty, inverted or non-finite numeric ranges,
    /// and empty categorical choices.
    pub fn new(dims: Vec<Dim>) -> Result<Space, String> {
        if dims.is_empty() {
            return Err("space needs at least one dimension".into());
        }
        for (i, d) in dims.iter().enumerate() {
            match d {
                Dim::Continuous { low, high } => {
                    if !low.is_finite() || !high.is_finite() {
                        return Err(format!("dim {i}: non-finite continuous bounds"));
                    }
                    if low > high {
                        return Err(format!("dim {i}: low {low} > high {high}"));
                    }
                }
                Dim::Integer { low, high } => {
                    if low > high {
                        return Err(format!("dim {i}: low {low} > high {high}"));
                    }
                }
                Dim::Categorical { choices } => {
                    if choices.is_empty() {
                        return Err(format!("dim {i}: categorical has no choices"));
                    }
                }
            }
        }
        Ok(Space { dims })
    }

    pub fn dims(&self) -> &[Dim] {
        &self.dims
    }

    pub fn len(&self) -> usize {
        self.dims.len()
    }

    pub fn is_empty(&self) -> bool {
        self.dims.is_empty()
    }

    /// Uniform random draw, one value per dimension, in declared order.
    pub fn sample(&self, rng: &mut Rng) -> Vec<Value> {
        self.dims
            .iter()
            .map(|d| match d {
                Dim::Continuous { low, high } => Value::Real(rng.next_range(*low, *high)),
                Dim::Integer { low, high } => {
                    let n = (*high - *low + 1) as u64;
                    Value::Int(*low + rng.below(n) as i64)
                }
                Dim::Categorical { choices } => {
                    Value::Cat(rng.below(choices.len() as u64) as usize)
                }
            })
            .collect()
    }

    /// True if every value matches its dimension's type and bounds. Used
    /// to validate resumed logs.
    pub fn contains(&self, params: &[Value]) -> bool {
        if params.len() != self.dims.len() {
            return false;
        }
        self.dims.iter().zip(params).all(|(d, v)| match (d, v) {
            (Dim::Continuous { low, high }, Value::Real(x)) => low <= x && x <= high,
            (Dim::Integer { low, high }, Value::Int(x)) => low <= x && x <= high,
            (Dim::Categorical { choices }, Value::Cat(k)) => *k < choices.len(),
            _ => false,
        })
    }
}

/// Canonical dedup key for a parameter vector — the exact JSON encoding,
/// so "already evaluated" is byte-stable across runs and processes.
pub fn params_key(params: &[Value]) -> String {
    serde_json::to_string(params).expect("Value is always JSON-serializable")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_bad_spaces() {
        assert!(Space::new(vec![]).is_err());
        assert!(Space::new(vec![Dim::Integer { low: 10, high: 1 }]).is_err());
        assert!(Space::new(vec![Dim::Categorical { choices: vec![] }]).is_err());
        assert!(Space::new(vec![Dim::Continuous { low: 1.0, high: -1.0 }]).is_err());
    }

    #[test]
    fn sample_respects_bounds() {
        let space = Space::new(vec![
            Dim::Continuous { low: -2.5, high: 2.5 },
            Dim::Integer { low: 3, high: 7 },
            Dim::Categorical { choices: vec!["a".into(), "b".into(), "c".into()] },
        ])
        .unwrap();
        let mut rng = Rng::new(11);
        for _ in 0..1000 {
            let p = space.sample(&mut rng);
            assert!(space.contains(&p));
        }
    }

    #[test]
    fn value_json_is_externally_tagged() {
        // The lab artifacts read back params as {"Int": n} / {"Cat": k}.
        let s = serde_json::to_string(&vec![Value::Int(8), Value::Cat(2)]).unwrap();
        assert_eq!(s, r#"[{"Int":8},{"Cat":2}]"#);
    }
}
