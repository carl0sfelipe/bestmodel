//! Pool snapshot loading: the in-repo `apps/web/data/derived/pool.json`
//! shape must convert honestly into run entries (source_class=harvested,
//! cells without a decode median dropped) and rank through `suggest`.

use canirunit::{runs_from_pool, suggest, PoolFile};

#[test]
fn pool_converts_to_harvested_runs() {
    let raw = std::fs::read_to_string("tests/fixtures/pool-snapshot.json").unwrap();
    let pool: PoolFile = serde_json::from_str(&raw).unwrap();
    let runs = runs_from_pool(&pool);

    // the m4 cell has no tokSOutMedian: dropped, not zero-filled
    assert_eq!(runs.len(), 2);
    assert!(runs.iter().all(|r| r.source_class == "harvested"));
    assert!(runs.iter().all(|r| r.gpu_model_id == "rtx-3090-24gb"));
    assert_eq!(runs[0].decode_tok_s, Some(44.2));
    assert_eq!(runs[0].run_id, "rtx-3090-24gb/qwen3-8b-q4");
}

#[test]
fn suggest_ranks_over_pool_runs() {
    let raw = std::fs::read_to_string("tests/fixtures/pool-snapshot.json").unwrap();
    let pool: PoolFile = serde_json::from_str(&raw).unwrap();
    let runs = runs_from_pool(&pool);

    let outcome = suggest("rtx-3090-24gb", "decode_tok_s", &runs).unwrap();
    assert_eq!(outcome.match_class, "exact_gpu");
    assert_eq!(outcome.suggestions.len(), 2);
    // higher decode wins
    assert_eq!(outcome.suggestions[0].model_release_id, "qwen3-8b-q4");
    assert_eq!(outcome.suggestions[0].source_class, "harvested");
    assert!(outcome.suggestions[0].explanation.contains("harvested"));

    // unknown GPU: honest empty outcome
    let miss = suggest("rtx-5090-32gb", "decode_tok_s", &runs).unwrap();
    assert_eq!(miss.match_class, "unknown");
    assert!(miss.suggestions.is_empty());
}
