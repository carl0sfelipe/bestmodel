BEGIN;

-- S30: OAuth sign-in (GitHub, Hugging Face). One row per external identity;
-- (provider, provider_account_id) is the login key, so a second visit maps
-- back to the same app_user. Handles may collide with passkey accounts —
-- resolution (suffixing) happens in the service layer, not here.

CREATE TABLE oauth_account (
  id UUID PRIMARY KEY,
  app_user_id UUID NOT NULL REFERENCES app_user(id),
  provider TEXT NOT NULL CHECK (provider IN ('github', 'huggingface')),
  provider_account_id TEXT NOT NULL,
  login TEXT NOT NULL,
  display_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_account_id)
);

COMMIT;
