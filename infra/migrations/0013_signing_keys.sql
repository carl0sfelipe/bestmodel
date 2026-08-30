-- Story S23: per-user signing keys — cryptographic attribution of submitted
-- runs to app users. Today every submission is verified against ONE global
-- trusted key (TRUSTED_ED25519_PUBLIC_KEY_PATH): client authenticity, not
-- user authorship. This migration adds the signing_key table and the
-- OPTIONAL benchmark_run.signature_key_id (D2: opt-in — legacy global-key
-- submissions stay valid; NULL means the legacy path).
-- Lockstep (packages/domain-schema/AGENTS.md): run_record.py, both session
-- implementations and the round-trip test change in the same commit.
BEGIN;

CREATE TABLE IF NOT EXISTS signing_key (
  id UUID PRIMARY KEY,
  app_user_id UUID NOT NULL REFERENCES app_user(id),
  label TEXT NOT NULL,
  public_key_pem TEXT NOT NULL,
  algorithm TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS signing_key_user_idx
  ON signing_key (app_user_id) WHERE revoked_at IS NULL;

ALTER TABLE benchmark_run
  ADD COLUMN IF NOT EXISTS signature_key_id UUID REFERENCES signing_key(id);

COMMIT;
