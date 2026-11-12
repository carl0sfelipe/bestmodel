"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import Composer from "./composer";
import {
  beginOAuth,
  consumeOAuthFragment,
  fetchSession,
  loginPasskey,
  passkeySupported,
  registerPasskey,
  type SessionInfo,
} from "../../lib/auth";
import {
  ago,
  fetchFeed,
  fetchNotifications,
  getToken,
  getUser,
  markNotificationRead,
  setToken,
  type FeedItem,
  type FeedScope,
  type FeedSort,
  type NotificationRow,
} from "../../lib/social";

type Tab = "feed" | "notifications" | "profile";

export default function ConsoleClient() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [checked, setChecked] = useState(false);
  const [tab, setTab] = useState<Tab>("feed");
  const [feedKey, setFeedKey] = useState(0);

  useEffect(() => {
    let alive = true;
    // an OAuth callback leaves the token in the fragment; pick it up first
    try {
      consumeOAuthFragment();
    } catch {
      /* the fragment carried an error; the sign-in card shows the state */
    }
    const token = getToken();
    if (!token) {
      setChecked(true);
      return;
    }
    fetchSession()
      .then((info) => {
        if (!alive) return;
        setSession(info);
        setChecked(true);
      })
      .catch(() => {
        if (!alive) return;
        setSession(null);
        setChecked(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  const signOut = useCallback(() => {
    setToken(null);
    setSession(null);
    setTab("feed");
  }, []);

  if (!checked) {
    return (
      <main>
        <section className="desk-head">
          <h1 className="desk-title">Console</h1>
        </section>
        <div className="skel" aria-hidden="true">
          <div className="skel-row" />
        </div>
      </main>
    );
  }

  if (!session) {
    return <SignIn onSignedIn={(next) => setSession(next)} />;
  }

  return (
    <main>
      <section className="desk-head">
        <div className="desk-id">
          <h1 className="desk-title">@{session.handle}</h1>
          <p className="desk-sub">
            {session.reputation?.tier ? `${session.reputation.tier} · ` : ""}
            {session.reputation?.points ?? 0} points ·{" "}
            <Link href={`/profile/${session.handle}`}>public profile</Link>
          </p>
        </div>
        <button className="btn" type="button" onClick={signOut}>
          Sign out
        </button>
      </section>

      <div className="desk">
        <nav className="desk-rail" aria-label="Console sections">
          {(
            [
              ["feed", "feed"],
              ["notifications", "notifications"],
              ["profile", "profile"],
            ] as Array<[Tab, string]>
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className="desk-tab"
              aria-pressed={tab === id}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
          <Link className="btn primary desk-cta" href="/submit">
            capture a run
          </Link>
        </nav>

        <div className="desk-panel">
          {tab === "feed" && (
            <>
              <Composer onPosted={() => setFeedKey((value) => value + 1)} />
              <Feed key={feedKey} />
            </>
          )}
          {tab === "notifications" && <Notifications />}
          {tab === "profile" && <Profile handle={session.handle} />}
        </div>
      </div>
    </main>
  );
}

// ------------------------------------------------------------------- sign in

function SignIn({ onSignedIn }: { onSignedIn: (session: SessionInfo) => void }) {
  const [handle, setHandle] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [problem, setProblem] = useState(false);
  const supported = passkeySupported();

  async function run(action: "register" | "login") {
    setBusy(true);
    setMessage(null);
    const result =
      action === "register" ? await registerPasskey(handle) : await loginPasskey(handle);
    setBusy(false);
    if (!result.ok) {
      setMessage(result.detail);
      return;
    }
    if (action === "register") {
      // registration proves the key, not a session — sign in right after
      const signed = await loginPasskey(handle);
      if (!signed.ok) {
        setMessage(`Account created. ${signed.detail}`);
        return;
      }
    }
    const resolved = await fetchSession();
    onSignedIn(resolved ?? { handle: handle.trim().toLowerCase() });
  }

  return (
    <main>
      <section className="desk-head">
        <h1 className="desk-title">Sign in to the network</h1>
        <p className="desk-sub">
          An account is a handle and a passkey. No email, no password — the key stays on your
          device. With one you can vote on claims, follow rigs and people, and post your own
          measurements for the community to judge.
        </p>
      </section>

      <section className="desk-panel desk-signin">
        {!supported && (
          <p className="banner" data-k="bad">
            This browser has no passkey support. Open the site in a current browser on a device with
            a screen lock, or sign in with a provider below.
          </p>
        )}

        <div className="field">
          <label htmlFor="console-handle">handle</label>
          <input
            id="console-handle"
            value={handle}
            onChange={(event) => setHandle(event.target.value)}
            placeholder="lowercase, 2–32 chars"
            autoComplete="username"
            spellCheck={false}
          />
          <span className="help">
            Letters, digits, dash and underscore. This is the name other people see.
          </span>
        </div>

        <div className="desk-actions">
          <button
            className="btn primary"
            type="button"
            disabled={busy || !handle.trim()}
            onClick={() => run("register")}
          >
            {busy ? "working…" : "Create account with a passkey"}
          </button>
          <button
            className="btn"
            type="button"
            disabled={busy || !handle.trim()}
            onClick={() => run("login")}
          >
            Sign in
          </button>
        </div>

        <p className="hint">or sign in with a provider:</p>
        <div className="desk-actions">
          <button className="btn" type="button" onClick={() => beginOAuth("github")}>
            GitHub
          </button>
          <button className="btn" type="button" onClick={() => beginOAuth("huggingface")}>
            Hugging Face
          </button>
        </div>

        {message && (
          <p className="banner" data-k={problem ? "bad" : "note"} role="status">
            {message}
          </p>
        )}
      </section>

      <section className="desk-aside">
        <h2 className="craft-head">What an account is for</h2>
        <ul className="desk-list">
          <li>
            <strong>Vote.</strong> A claim is a number somebody asserts. Plausible or impossible —
            your weight comes from your reputation tier.
          </li>
          <li>
            <strong>Be followed.</strong> People follow rigs and hands, not benchmarks.
          </li>
          <li>
            <strong>Capture.</strong> Post a run you measured; a signed CLI run can settle it for
            good.
          </li>
        </ul>
        <p className="desk-note">
          Reads need no account. Only writes do — the wall, the pool and the catalogue are open to
          everyone.
        </p>
      </section>
    </main>
  );
}

// ---------------------------------------------------------------------- feed

function Feed() {
  const [scope, setScope] = useState<FeedScope>("global");
  const [sort, setSort] = useState<FeedSort>("recent");
  const [items, setItems] = useState<FeedItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setItems(null);
    setError(null);
    fetchFeed({ scope, sort })
      .then((result) => {
        if (!alive) return;
        if (!result.ok) {
          setError(result.detail ?? "The feed could not be loaded.");
          setItems([]);
          return;
        }
        setItems(result.data ?? []);
      })
      .catch(() => {
        if (!alive) return;
        setError("The feed could not be loaded.");
        setItems([]);
      });
    return () => {
      alive = false;
    };
  }, [scope, sort]);

  return (
    <section>
      <div className="ctl-bar">
        <div className="ctl-group">
          <span className="ctl-label">scope</span>
          <div className="opt-row" role="group" aria-label="Feed scope">
            {(
              [
                ["global", "everyone"],
                ["following", "following"],
              ] as Array<[FeedScope, string]>
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                className="opt"
                aria-pressed={scope === value}
                onClick={() => setScope(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="ctl-group">
          <span className="ctl-label">ordering</span>
          <div className="opt-row" role="group" aria-label="Feed ordering">
            {(
              [
                ["recent", "most recent"],
                ["trending", "most active"],
              ] as Array<[FeedSort, string]>
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                className="opt"
                aria-pressed={sort === value}
                onClick={() => setSort(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <p className="banner" data-k="bad" role="status">
          {error}
        </p>
      )}

      {items === null ? (
        <div className="skel" aria-hidden="true">
          <div className="skel-row" />
          <div className="skel-row" />
        </div>
      ) : items.length === 0 ? (
        <div className="empty">
          <p className="empty-mark">···</p>
          <h2>{scope === "following" ? "Nobody followed yet" : "Nothing here yet"}</h2>
          <p>
            {scope === "following"
              ? "Follow a rig or a hand and their captures land here."
              : "The feed fills up as people capture runs. Be the first."}
          </p>
          <div className="actions">
            <Link className="btn" href="/claims">
              the wall
            </Link>
            <Link className="btn primary" href="/submit">
              capture a run
            </Link>
          </div>
        </div>
      ) : (
        <div className="claim-list">
          {items.map((item) =>
            item.type === "post" ? (
              <article className="claim-card" key={`post-${item.id}`}>
                <div className="claim-top">
                  <Link className="claim-who" href={`/p/${item.id}`}>
                    {item.handle ? `@${item.handle}` : "member"}
                  </Link>
                  <span className="post-kind">{item.post_kind}</span>
                  <span className="claim-age">{ago(item.created_at) ?? ""}</span>
                </div>
                <Link className="claim-model claim-post-body" href={`/p/${item.id}`}>
                  {item.body}
                </Link>
                <p className="claim-meta">
                  {item.comment_count} comments · {item.like_count} likes
                  {item.claim_id ? (
                    <>
                      {" · "}
                      <Link href={`/claim/${item.claim_id}`}>about a claim</Link>
                    </>
                  ) : null}
                  {item.model_release_id ? (
                    <>
                      {" · "}
                      <Link href={`/m/${item.model_release_id}`}>{item.model_release_id}</Link>
                    </>
                  ) : null}
                </p>
              </article>
            ) : item.type === "claim" ? (
              <article className="claim-card" key={`claim-${item.id}`}>
                <div className="claim-top">
                  <Link className="claim-who" href={`/claim/${item.id}`}>
                    {item.handle ? `@${item.handle}` : "imported"}
                  </Link>
                  <span className="status" data-s={item.status}>
                    {item.status.replace("_", " ")}
                  </span>
                  <span className="claim-age">{ago(item.created_at) ?? ""}</span>
                </div>
                <Link className="claim-model" href={`/claim/${item.id}`}>
                  {item.model_release_id}
                </Link>
                <div className="claim-num">
                  {item.claimed_metrics?.decode_tok_s ?? "—"}
                  <small>tok/s decode · claimed</small>
                </div>
                {item.tally && (
                  <div className="tally">
                    <div className="tally-bar">
                      <i
                        className="yes"
                        style={{ width: `${pct(item.tally.plausible_count, item.tally.impossible_count)}%` }}
                      />
                      <i className="no" style={{ width: `${100 - pct(item.tally.plausible_count, item.tally.impossible_count)}%` }} />
                    </div>
                    <div className="tally-legend">
                      <span className="yes">{item.tally.plausible_count ?? 0} plausible</span>
                      <span className="no">{item.tally.impossible_count ?? 0} impossible</span>
                    </div>
                  </div>
                )}
              </article>
            ) : (
              <article className="claim-card" key={`run-${item.run_id}`}>
                <div className="claim-top">
                  <span className="claim-who imported">signed run</span>
                  <span className="status" data-s="settled_verified">
                    measured
                  </span>
                  <span className="claim-age">{ago(item.submitted_at) ?? ""}</span>
                </div>
                <Link className="claim-model" href={`/m/${item.model_release_id}`}>
                  {item.model_release_id}
                </Link>
                <div className="claim-num">
                  {item.decode_tok_s ?? "—"}
                  <small>tok/s decode · measured</small>
                </div>
              </article>
            ),
          )}
        </div>
      )}
    </section>
  );
}

function pct(yes?: number | null, no?: number | null): number {
  const a = yes ?? 0;
  const b = no ?? 0;
  const total = a + b;
  if (total === 0) return 50;
  return Math.round((a / total) * 100);
}

// ------------------------------------------------------------- notifications

function Notifications() {
  const [rows, setRows] = useState<NotificationRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetchNotifications()
      .then((result) => {
        if (!alive) return;
        if (!result.ok) {
          setError(result.detail ?? "Notifications could not be loaded.");
          setRows([]);
          return;
        }
        setRows(result.data ?? []);
      })
      .catch(() => {
        if (!alive) return;
        setError("Notifications could not be loaded.");
        setRows([]);
      });
    return () => {
      alive = false;
    };
  }, []);

  async function markRead(id: string) {
    const result = await markNotificationRead(id);
    if (!result.ok) {
      setError(result.detail ?? "The notification could not be marked as read.");
      return;
    }
    setRows((current) =>
      (current ?? []).map((row) => (row.id === id ? { ...row, read_at: row.read_at ?? "now" } : row)),
    );
  }

  if (error) {
    return (
      <p className="banner" data-k="bad" role="status">
        {error}
      </p>
    );
  }
  if (rows === null) {
    return (
      <div className="skel" aria-hidden="true">
        <div className="skel-row" />
      </div>
    );
  }
  if (rows.length === 0) {
    return (
      <div className="empty">
        <p className="empty-mark">···</p>
        <h2>No notifications yet</h2>
        <p>New followers, settled claims and refuted numbers land here.</p>
      </div>
    );
  }
  return (
    <ul className="desk-list desk-notifications">
      {rows.map((row) => (
        <li key={row.id} className={row.read_at ? "read" : ""}>
          <span className="desk-notif-kind">{kindLabel(row.kind)}</span>
          <span className="desk-notif-body">{describeNotification(row)}</span>
          <span className="desk-notif-age">{ago(row.created_at) ?? ""}</span>
          {!row.read_at && (
            <button className="btn" type="button" onClick={() => markRead(row.id)}>
              Mark read
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

function kindLabel(kind: string): string {
  switch (kind) {
    case "new_follower":
      return "new follower";
    case "claim_settled_verified":
      return "claim measured";
    case "claim_refuted":
      return "claim refuted";
    case "duel_result":
      return "duel";
    default:
      return kind;
  }
}

function describeNotification(row: NotificationRow): React.ReactNode {
  const payload = row.payload ?? {};
  const handle = typeof payload.handle === "string" ? payload.handle : null;
  const claimId = typeof payload.claim_id === "string" ? payload.claim_id : null;
  if (row.kind === "new_follower") {
    return handle ? `@${handle} started following you.` : "Someone started following you.";
  }
  if (claimId) {
    return (
      <>
        A claim of yours changed state.{" "}
        <Link href={`/claim/${claimId}`}>open it</Link>
      </>
    );
  }
  return "Something happened on the wall.";
}

// ------------------------------------------------------------------ profile

function Profile({ handle }: { handle: string }) {
  const [profile, setProfile] = useState<{
    display_name?: string | null;
    created_at?: string | null;
    reputation?: { points?: number | null; tier?: string | null } | null;
    badges?: unknown[] | null;
    rigs?: Array<{ slug: string; nickname?: string | null }> | null;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getUser(handle)
      .then((result) => {
        if (!alive) return;
        if (!result.ok || !result.data) {
          setError(result.detail ?? "The profile could not be loaded.");
          setProfile(null);
          return;
        }
        setProfile(result.data);
      })
      .catch(() => {
        if (!alive) return;
        setError("The profile could not be loaded.");
      });
    return () => {
      alive = false;
    };
  }, [handle]);

  if (error) {
    return (
      <p className="banner" data-k="bad" role="status">
        {error}
      </p>
    );
  }
  if (!profile) {
    return (
      <div className="skel" aria-hidden="true">
        <div className="skel-row" />
      </div>
    );
  }
  return (
    <section>
      <dl className="defs">
        <div>
          <dt>handle</dt>
          <dd>@{handle}</dd>
        </div>
        <div>
          <dt>tier</dt>
          <dd>{profile.reputation?.tier ?? "L0"}</dd>
        </div>
        <div>
          <dt>points</dt>
          <dd>{profile.reputation?.points ?? 0}</dd>
        </div>
        <div>
          <dt>badges</dt>
          <dd>{profile.badges?.length ?? 0}</dd>
        </div>
        <div>
          <dt>rigs</dt>
          <dd>{profile.rigs?.length ?? 0}</dd>
        </div>
      </dl>
      <p className="desk-note">
        <Link href={`/profile/${handle}`}>open the public profile</Link>
      </p>
    </section>
  );
}
