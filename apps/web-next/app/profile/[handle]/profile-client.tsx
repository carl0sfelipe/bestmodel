"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Banner, EmptyState, Skeleton, fmt } from "../../../components/claim-parts";
import {
  ago,
  CONSOLE_HREF,
  getToken,
  getUser,
  setFollow,
  type Badge,
  type UserProfile,
} from "../../../lib/social";

/**
 * The ladder. Copy is frozen and owner-approved — do not reword.
 * A rung is only ever "held" when the API says it was granted. An ungranted
 * rung renders as "not yet"; it is never hidden, because hiding it would let
 * the page imply a level the pool never conferred.
 */
const RUNGS = [
  {
    key: "contributor",
    level: "level 01",
    name: "Contributor",
    blurb:
      "You run benchmarks on your own hardware and submit signed results. One machine, one voice, but a real one on the record.",
    granted: "granted by: a validated signed run",
  },
  {
    key: "replicator",
    level: "level 02",
    name: "Replicator",
    blurb:
      "You independently reproduce other contributors' runs, confirming or contradicting reported numbers.",
    granted: "granted by: validated reproductions",
  },
  {
    key: "auditor",
    level: "level 03",
    name: "Auditor",
    blurb:
      "You defend the pool: replicate high-impact cells and report unreal runs through moderation.",
    granted: "granted by: confirmed fake caught + reproductions",
  },
] as const;

/** A rung counts as held only when a badge from the API names it. No inference. */
function heldRungs(badges: Badge[] | null | undefined): Set<string> {
  const held = new Set<string>();
  for (const badge of badges ?? []) {
    for (const value of Object.values(badge ?? {})) {
      if (typeof value !== "string") continue;
      const needle = value.toLowerCase();
      for (const rung of RUNGS) {
        if (needle.includes(rung.key)) held.add(rung.key);
      }
    }
  }
  return held;
}

export default function ProfileClient({ handle }: { handle: string }) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<{ status: number; detail: string } | null>(null);
  const [signedIn, setSignedIn] = useState(false);

  const [following, setFollowing] = useState(false);
  const [followBusy, setFollowBusy] = useState(false);
  const [followError, setFollowError] = useState<string | null>(null);

  useEffect(() => setSignedIn(getToken() != null), []);

  const load = useCallback(async () => {
    const result = await getUser(handle);
    if (result.ok && result.data) {
      setProfile(result.data);
      setFollowing(Boolean(result.data.follow?.viewer_is_following));
      setLoadError(null);
    } else {
      setLoadError({ status: result.status, detail: result.detail ?? "Unknown error." });
    }
    setLoading(false);
  }, [handle]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggleFollow() {
    setFollowBusy(true);
    setFollowError(null);
    const next = !following;
    const result = await setFollow(handle, next);
    setFollowBusy(false);
    if (result.ok) {
      setFollowing(next);
      await load();
      return;
    }
    setFollowError(result.detail);
  }

  if (loading) {
    return (
      <main>
        <section className="page-head">
          <p className="kicker">bestmodel.run / track record</p>
        </section>
        <Skeleton rows={2} />
      </main>
    );
  }

  if (loadError?.status === 404) {
    return (
      <main>
        <section className="page-head">
          <p className="kicker">bestmodel.run / track record</p>
        </section>
        <EmptyState
          mark="404"
          title="No such handle."
          body={`Nobody is registered as @${handle}. The link may be wrong, or the account may never have existed.`}
          action={
            <Link className="btn primary" href="/claims">
              Back to the wall
            </Link>
          }
        />
      </main>
    );
  }

  if (!profile) {
    return (
      <main>
        <section className="page-head">
          <p className="kicker">bestmodel.run / track record</p>
        </section>
        <Banner kind="bad">
          <b>this profile could not be loaded</b> — {loadError?.detail}
        </Banner>
      </main>
    );
  }

  const held = heldRungs(profile.badges);
  const publicRigs = (profile.rigs ?? []).filter((rig) => rig.is_public);
  const joined = ago(profile.created_at);

  return (
    <main>
      <section className="page-head">
        <p className="kicker">bestmodel.run / track record</p>
        <h1>@{profile.handle}</h1>
        <p>
          {profile.display_name ? `${profile.display_name}. ` : ""}
          Trust here is a ladder, climbed by verified acts. Every level is granted by a verified
          act, is never self-declared, does not decay, and every act is attributable to an Ed25519
          key.
        </p>

        <div className="actions">
          {signedIn ? (
            <button
              type="button"
              className={following ? "btn on" : "btn primary"}
              disabled={followBusy}
              onClick={() => void toggleFollow()}
            >
              {followBusy ? "Working…" : following ? "Following" : "Follow"}
            </button>
          ) : (
            <Link className="btn" href={CONSOLE_HREF}>
              Sign in to follow
            </Link>
          )}
        </div>
        {followError && (
          <p className="help err" role="alert">
            {followError}
          </p>
        )}
      </section>

      {/* Facts the API stated, and nothing else. */}
      <section className="panel">
        <p className="panel-t">standing</p>
        <div className="figs">
          <div className="fig">
            <span className="v">{fmt(profile.reputation?.points ?? 0, 0)}</span>
            <span className="k">points</span>
          </div>
          <div className="fig">
            <span className="v">{profile.reputation?.tier ?? "—"}</span>
            <span className="k">tier</span>
          </div>
          <div className="fig">
            <span className="v">{fmt(profile.follow?.followers ?? 0, 0)}</span>
            <span className="k">followers</span>
          </div>
          <div className="fig">
            <span className="v">{fmt(profile.follow?.following ?? 0, 0)}</span>
            <span className="k">following</span>
          </div>
        </div>
        {joined && <p className="note">joined {joined}</p>}
      </section>

      <section className="section">
        <h2>The ladder</h2>
        <p className="section-copy">
          Granted by a verified act; levels are not self-declared and do not decay; every act is
          attributable to an Ed25519 key.
        </p>
        <div className="ladder" style={{ marginTop: 28 }}>
          {RUNGS.map((rung) => {
            const isHeld = held.has(rung.key);
            return (
              <article className="rung" key={rung.key} data-state={isHeld ? "held" : "not-yet"}>
                <small className="kicker">{rung.level}</small>
                <h3>{rung.name}</h3>
                <p>{rung.blurb}</p>
                <span className="granted">{isHeld ? rung.granted : "not yet"}</span>
              </article>
            );
          })}
        </div>
      </section>

      <section className="section">
        <h2>Public rigs</h2>
        {publicRigs.length === 0 ? (
          <p className="section-copy">
            No public rig on this profile. A rig only appears here when its owner marks it public.
          </p>
        ) : (
          <div className="claim-list" style={{ marginTop: 24 }}>
            {publicRigs.map((rig) => (
              <article className="claim-card" key={rig.slug}>
                <div className="claim-model">{rig.nickname ?? rig.slug}</div>
                <div className="claim-meta">
                  {rig.slug}
                  {rig.created_at ? ` · registered ${ago(rig.created_at)}` : ""}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
