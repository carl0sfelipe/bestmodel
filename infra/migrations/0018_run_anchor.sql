-- 0018: run_anchor — Bitcoin-anchored evidence for validated runs (EaaS B1).
-- A validated run gets its canonical payload digest registered in the
-- EaaS engine (POST /v1/records, kind=benchmark); the Merkle proof and
-- btc txid live in the engine's verify-api, reachable by record_id.
CREATE TABLE run_anchor (
  benchmark_run_id UUID PRIMARY KEY REFERENCES benchmark_run(id),
  digest TEXT NOT NULL,
  record_id TEXT NOT NULL,
  studio_id TEXT NOT NULL,
  anchored_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
