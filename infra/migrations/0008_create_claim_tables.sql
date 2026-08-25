BEGIN;

-- S15 (L02): run claims ("claimed" track, never mixed into validated
-- leaderboards) and community plausibility votes.
--
-- prior_snapshot freezes what our own data predicted at claim creation time;
-- it is never recomputed when predictors improve (L02 rule).
-- Vote weight is bounded to (0, 1] so a single high-reputation voter cannot
-- outvote an arbitrarily large group by themselves.

CREATE TABLE run_claim (
  id UUID PRIMARY KEY,
  claimant_id UUID NOT NULL REFERENCES app_user(id),
  rig_id UUID REFERENCES rig(id),
  model_release_id TEXT NOT NULL REFERENCES model_release(id),
  quantization_profile_id TEXT REFERENCES quantization_profile(id),
  inference_runtime_id TEXT REFERENCES inference_runtime(id),
  gpu_model_id TEXT REFERENCES gpu_model(id),
  context_tokens INT CHECK (context_tokens IS NULL OR context_tokens > 0),
  claimed_metrics JSONB NOT NULL,
  note TEXT,
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'settled_verified', 'refuted', 'retracted')),
  prior_snapshot JSONB NOT NULL,
  benchmark_run_id UUID REFERENCES benchmark_run(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX run_claim_status_idx ON run_claim(status);
CREATE INDEX run_claim_claimant_idx ON run_claim(claimant_id);

CREATE TABLE claim_vote (
  id UUID PRIMARY KEY,
  run_claim_id UUID NOT NULL REFERENCES run_claim(id),
  voter_id UUID NOT NULL REFERENCES app_user(id),
  verdict TEXT NOT NULL CHECK (verdict IN ('plausible', 'impossible')),
  weight NUMERIC(5,4) NOT NULL CHECK (weight > 0 AND weight <= 1),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (run_claim_id, voter_id)
);

COMMIT;
