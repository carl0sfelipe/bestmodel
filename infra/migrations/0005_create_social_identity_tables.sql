BEGIN;

-- S13 (L02): social identity core. Rigs, claims, votes and follows arrive in
-- later additive migrations (S14/S15) per specs/en/L02-social-platform.md.

CREATE TABLE app_user (
  id UUID PRIMARY KEY,
  handle TEXT NOT NULL UNIQUE
    CHECK (handle ~ '^[a-z0-9][a-z0-9_-]{1,31}$'),
  display_name TEXT NOT NULL CHECK (length(display_name) BETWEEN 1 AND 64),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_reputation (
  app_user_id UUID PRIMARY KEY REFERENCES app_user(id),
  points INT NOT NULL DEFAULT 0 CHECK (points >= 0),
  tier TEXT NOT NULL DEFAULT 'L0'
    CHECK (tier IN ('L0', 'L1', 'L2', 'L3', 'L4')),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reputation_event (
  id UUID PRIMARY KEY,
  app_user_id UUID NOT NULL REFERENCES app_user(id),
  reason TEXT NOT NULL
    CHECK (reason IN (
      'account_created', 'verified_run_published', 'claim_created',
      'claim_settled_verified', 'claim_refuted_own', 'vote_cast',
      'duel_won', 'badge_awarded', 'moderator_adjustment'
    )),
  delta INT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
