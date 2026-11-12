BEGIN;

-- L08: the classic social layer — posts, comments and likes.
--
-- A post carries TEXT only. Numbers belong to claims: a post may reference a
-- claim, a rig or a model, never carry a measurement of its own. Deletion is
-- soft (spam only); honest-but-wrong stays visible. Comment threads are one
-- level deep: a comment answers a post or another comment, and a reply to a
-- reply attaches to the same parent.

CREATE TABLE post (
  id UUID PRIMARY KEY,
  author_id UUID NOT NULL REFERENCES app_user(id),
  body TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
  kind TEXT NOT NULL DEFAULT 'note'
    CHECK (kind IN ('note', 'question', 'showcase')),
  claim_id UUID REFERENCES run_claim(id),
  rig_slug TEXT,
  model_release_id TEXT REFERENCES model_release(id),
  comment_count INT NOT NULL DEFAULT 0 CHECK (comment_count >= 0),
  like_count INT NOT NULL DEFAULT 0 CHECK (like_count >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ
);

CREATE INDEX post_created_idx ON post(created_at DESC);
CREATE INDEX post_author_idx ON post(author_id, created_at DESC);

CREATE TABLE comment (
  id UUID PRIMARY KEY,
  post_id UUID NOT NULL REFERENCES post(id),
  author_id UUID NOT NULL REFERENCES app_user(id),
  parent_id UUID REFERENCES comment(id),
  body TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 1000),
  like_count INT NOT NULL DEFAULT 0 CHECK (like_count >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ
);

CREATE INDEX comment_post_idx ON comment(post_id, created_at);
CREATE INDEX comment_author_idx ON comment(author_id);

CREATE TABLE post_like (
  post_id UUID NOT NULL REFERENCES post(id),
  user_id UUID NOT NULL REFERENCES app_user(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (post_id, user_id)
);

CREATE INDEX post_like_user_idx ON post_like(user_id, created_at DESC);

CREATE TABLE comment_like (
  comment_id UUID NOT NULL REFERENCES comment(id),
  user_id UUID NOT NULL REFERENCES app_user(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (comment_id, user_id)
);

CREATE INDEX comment_like_user_idx ON comment_like(user_id, created_at DESC);

-- The notification kinds the classic layer needs. The CHECK on
-- notification.kind is extended, never replaced.
ALTER TABLE notification DROP CONSTRAINT notification_kind_check;
ALTER TABLE notification ADD CONSTRAINT notification_kind_check CHECK (kind IN (
  'claim_settled_verified', 'claim_refuted', 'new_follower', 'duel_result',
  'post_commented', 'post_liked', 'comment_replied'
));

COMMIT;
