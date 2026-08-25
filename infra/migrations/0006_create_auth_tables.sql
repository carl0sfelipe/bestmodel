BEGIN;

-- S13 (L02): authentication storage. Passkey-first (WebAuthn) plus bearer
-- tokens for agents and short-lived passkey sessions. Tokens are stored as
-- SHA-256 hex digests; the plaintext is shown to the user exactly once.

CREATE TABLE webauthn_credential (
  id UUID PRIMARY KEY,
  app_user_id UUID NOT NULL REFERENCES app_user(id),
  credential_id BYTEA NOT NULL UNIQUE,
  public_key BYTEA NOT NULL,
  sign_count BIGINT NOT NULL DEFAULT 0,
  transports TEXT[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ
);

CREATE TABLE auth_challenge (
  challenge TEXT PRIMARY KEY,
  purpose TEXT NOT NULL CHECK (purpose IN ('registration', 'authentication')),
  app_user_id UUID NOT NULL REFERENCES app_user(id),
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE auth_token (
  id UUID PRIMARY KEY,
  app_user_id UUID NOT NULL REFERENCES app_user(id),
  kind TEXT NOT NULL DEFAULT 'agent' CHECK (kind IN ('agent', 'session')),
  token_hash TEXT NOT NULL UNIQUE,
  name TEXT CHECK (name IS NULL OR length(name) BETWEEN 1 AND 64),
  expires_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ
);

COMMIT;
