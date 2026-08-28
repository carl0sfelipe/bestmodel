-- Story 5.2: lightweight contributor accounts and the per-IP audit log that
-- backs the quota for `reported` submissions (FR-7). Tokens are stored only
-- as sha256 hashes; the log keeps one row per accepted reported submission so
-- the quota is auditable after the fact.
BEGIN;

CREATE TABLE IF NOT EXISTS contributor_account (
  id UUID PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  token_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reported_submission_log (
  id UUID PRIMARY KEY,
  contributor_id UUID NOT NULL REFERENCES contributor_account(id),
  benchmark_run_id UUID,
  ip_address TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS reported_submission_log_ip_idx
  ON reported_submission_log (ip_address, created_at);

COMMIT;
