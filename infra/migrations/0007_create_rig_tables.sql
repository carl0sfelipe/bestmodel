BEGIN;

-- S14 (L02): rigs + profile badges. A rig is a user-owned machine description;
-- binding to hardware_submission rows connects it to measured benchmark runs.
-- Follows arrive with the feed (S17).

CREATE TABLE rig (
  id UUID PRIMARY KEY,
  owner_id UUID NOT NULL REFERENCES app_user(id),
  nickname TEXT NOT NULL CHECK (length(nickname) BETWEEN 1 AND 64),
  slug TEXT NOT NULL UNIQUE
    CHECK (slug ~ '^[a-z0-9][a-z0-9-]{2,62}$'),
  topology JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_public BOOLEAN NOT NULL DEFAULT true,
  hardware_submission_id UUID REFERENCES hardware_submission(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX rig_owner_idx ON rig(owner_id);

CREATE TABLE badge (
  id UUID PRIMARY KEY,
  app_user_id UUID NOT NULL REFERENCES app_user(id),
  code TEXT NOT NULL
    CHECK (code IN (
      'first_verified_run', 'giant_killer', 'pool_contributor_100h',
      'claim_settler', 'rig_collector'
    )),
  awarded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (app_user_id, code)
);

COMMIT;
