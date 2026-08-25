BEGIN;

-- S17 (L02): social graph and notifications.

CREATE TABLE follow (
  id UUID PRIMARY KEY,
  follower_id UUID NOT NULL REFERENCES app_user(id),
  followee_id UUID NOT NULL REFERENCES app_user(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (follower_id, followee_id),
  CHECK (follower_id <> followee_id)
);

CREATE INDEX follow_followee_idx ON follow(followee_id);
CREATE INDEX follow_follower_idx ON follow(follower_id);

CREATE TABLE notification (
  id UUID PRIMARY KEY,
  recipient_id UUID NOT NULL REFERENCES app_user(id),
  kind TEXT NOT NULL
    CHECK (kind IN (
      'claim_settled_verified', 'claim_refuted', 'new_follower', 'duel_result'
    )),
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  read_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX notification_recipient_idx ON notification(recipient_id, created_at DESC);

COMMIT;
