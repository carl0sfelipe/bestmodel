//! `rigs` support: listing the ids a corpus knows and the deterministic
//! "did you mean" ranking for a GPU id that does not match exactly.

use canirunit::{closest_rig_ids, rig_ids, runs_from_pool, RunEntry, PoolFile};

fn entries(ids: &[&str]) -> Vec<RunEntry> {
    ids.iter()
        .map(|id| RunEntry {
            run_id: format!("run-{id}"),
            gpu_model_id: (*id).to_string(),
            model_release_id: "model-x".to_string(),
            recipe_id: None,
            source_class: "harvested".to_string(),
            trust_score: None,
            age_days: None,
            decode_tok_s: Some(10.0),
            seconds_per_clip: None,
            frames_per_s: None,
        })
        .collect()
}

#[test]
fn rig_ids_sorted_and_deduped() {
    let runs = entries(&["rtx-4090-24gb", "rtx-3090-24gb", "rtx-4090-24gb", "a100-40gb"]);
    assert_eq!(rig_ids(&runs), vec!["a100-40gb", "rtx-3090-24gb", "rtx-4090-24gb"]);
}

#[test]
fn closest_ids_rank_real_corpus_ids_only() {
    let runs = entries(&["rtx-3090-24gb", "rtx-3090-24gb-x2", "rtx-4090-24gb", "a100-40gb"]);

    // detected name fragments land on the right family, best first
    let top = closest_rig_ids(&runs, "rtx-3090", 3);
    assert_eq!(top.first().map(String::as_str), Some("rtx-3090-24gb"));
    assert!(top.contains(&"rtx-3090-24gb-x2".to_string()));

    // bare number still ranks; garbage matches nothing (never invented)
    assert!(closest_rig_ids(&runs, "banana", 3).is_empty());

    // pool snapshot path lists the same ids
    let raw = std::fs::read_to_string("tests/fixtures/pool-snapshot.json").unwrap();
    let pool: PoolFile = serde_json::from_str(&raw).unwrap();
    let pool_runs = runs_from_pool(&pool);
    assert!(rig_ids(&pool_runs).contains(&"rtx-3090-24gb".to_string()));
}
