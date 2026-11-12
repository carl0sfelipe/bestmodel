# L08 — Classic Social Layer (posts, comments, likes) on top of the capture network

> Phase 1+ story cluster. English. Builds on S13–S22 (accounts, rigs, claims,
> votes, follows, feed, notifications) and adds the social primitives a
> network needs: say something, answer someone, mark something as worth
> reading. Every social object stays anchored to the honesty ladder — a post
> is never a measurement, and a post that quotes a number must not present it
> as one.

## Objective

Turn the capture network into a **network people talk in**, not only a board
people file numbers on. Today a member can post a claim, vote on other
people's claims, follow rigs and people, and read a feed of claims. What
they cannot do is write a sentence, answer a question, or mark a post as
worth reading — which is what makes a place feel alive.

The classic layer is deliberately thin and deliberately tied to the existing
objects. A post may attach to a claim, a rig or a model; a comment may
answer a post. Nothing here invents a second notion of truth: posts carry
no numbers of their own, and a post that quotes a number links the claim it
quotes.

## User experience (target)

```text
/console            the desk: sign in, compose, feed, notifications
/console?view=feed  the unified stream: posts, claims, signed runs
/p/{id}             one post: body, attachments, comments, likes
```

Core loop:

1. **Post** — a member writes a note, a question or a showcase, optionally
   attaching the claim, rig or model it is about.
2. **Answer** — somebody comments; the author is notified.
3. **Mark** — a member likes a post or a comment; the author is notified.
4. **Read** — the unified feed mixes posts with claims and signed runs, and
   the "following" scope mixes the people they follow.

## Data model (migration 0018, additive)

| Table | Purpose |
|---|---|
| `post` | author FK, body, kind (note/question/showcase), optional claim FK, optional rig FK, optional model_release_id, reply count, created_at, deleted_at (soft delete for spam only) |
| `comment` | post FK, author FK, parent FK (nullable → one level of threading), body, created_at, deleted_at |
| `post_like` | post FK, user FK, unique(post, user) |
| `comment_like` | comment FK, user FK, unique(comment, user) |

Rules:

- A post body is text only. Numbers belong in claims; a post may reference
  one, never carry its own.
- Deletion is soft and spam-only. Honest-but-wrong stays visible, badged.
- Comment threads are one level deep: a comment may answer a post or a
  comment; a reply to a reply attaches to the same parent.
- Self-likes and self-comments are allowed (a reply to your own post is
  normal), but a like never counts twice.

## Service surface (apps/public-api, additive)

```
POST   /v1/posts                 { body, kind?, claim_id?, rig_slug?, model_release_id? }
GET    /v1/posts/{id}            one post with its comments and counts
DELETE /v1/posts/{id}            author only, soft delete (spam)
POST   /v1/posts/{id}/comments   { body, parent_id? }
POST   /v1/posts/{id}/likes      idempotent toggle → { liked, count }
POST   /v1/comments/{id}/likes   idempotent toggle → { liked, count }
```

The unified feed (`GET /v1/feed`) gains a `post` item type. The existing
item types (`claim`, `verified_run`) and their ordering are unchanged — this
is additive, and a feed that mixes in posts keeps the same `scope` and
`sort` semantics.

Writes require a bearer token. Reads are public.

## Anti-abuse

- Post rate limits scale with reputation, like every other write here: see
  `src/services/rate_limit_policy.py`. New accounts (L0) post rarely; a
  member who has earned a tier posts more.
- Comment rate limits are per hour and scale with tier.
- Body length is capped (2000 characters for a post, 1000 for a comment);
  the cap is enforced by the request model, not by the client.
- A post that attaches a claim may not restate a different number for it.

## Acceptance

```
make test                                   # unit + route suites green
apps/public-api/tests/test_social_posts.py  # the new suites
npm run build --prefix apps/web-next        # the front compiles
```

Route suites must cover: auth required on writes, body caps, self-comment
allowed, reply-to-comment attaches to the parent, like toggling is
idempotent, a post never appears in a validated leaderboard, the feed mixes
the three item types without breaking `scope`/`sort`, and the notification
rows land for the author.

## Boundary

Posts carry no numbers and no verdicts. Verification stays where it belongs:
a claim, a vote, a signed run. A post that claims a measurement is answered
with a link to a claim, not with agreement in the comments.

Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
