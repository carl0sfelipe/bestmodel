"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Banner, EmptyState, Skeleton, fmt } from "../../../components/claim-parts";
import {
  ago,
  CONSOLE_HREF,
  getToken,
  getUser,
  listClaims,
  setFollow,
  type Badge,
  type Claim,
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

  // What this account put on the wall. The API does not serve "claims by
  // handle", so the client reads the wall and keeps the rows whose claimant
  // handle matches. Only rows with a real claimant id count as this
  // person's — imports carry a label that is not an account.
  const [captures, setCaptures] = useState<Claim[] | null>(null);

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

  useEffect(() => {
    let alive = true;
    listClaims({ status: "", sort: "recent", limit: 100, offset: 0 })
      .then((result) => {
        if (!alive) return;
        const rows = result.data ?? [];
        setCaptures(
          rows.filter(
            (row) => row.claimant_id != null && row.claimant_handle === handle,
          ),
        );
      })
      .catch(() => {
        if (!alive) return;
        setCaptures([]);
      });
    return () => {
      alive = false;
    };
  }, [handle]);

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
          <p className="kicker">bestmodel.run / profile</p>
        </section>
        <Skeleton rows={2} />
      </main>
    );
  }

  if (loadError?.status === 404) {
    return (
      <main>
        <section className="page-head">
          <p className="kicker">bestmodel.run / profile</p>
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
          <p className="kicker">bestmodel.run / profile</p>
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
  const captureCount = captures?.length ?? 0;

  return (
    <main>
      {/* the record sheet header: who, since when, and the one action */}
      <section className="sheet-head">
        <div className="record-head">
          <div className="record-id">
            <p className="overline">account</p>
            <h1 className="record-name">@{profile.handle}</h1>
            <p className="record-sub">
              {profile.display_name ? `${profile.display_name}. ` : ""}
              Trust here is a ladder, climbed by verified acts. Every level is granted by a
              verified act, is never self-declared, does not decay, and every act is attributable
              to an Ed25519 key.
              {joined ? ` Joined ${joined}.` : ""}
            </p>
          </div>
          <div className="record-actions">
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
        </div>
        {followError && (
          <p className="help err" role="alert">
            {followError}
          </p>
        )}
      </section>

      {/* standing: a strip of figures, not a card grid */}
      <section className="record-strip" aria-label="Standing">
        <div className="record-fig">
          <span className="v">{fmt(profile.reputation?.points ?? 0, 0)}</span>
          <span className="k">points</span>
        </div>
        <div className="record-fig">
          <span className="v">{profile.reputation?.tier ?? "—"}</span>
          <span className="k">tier</span>
        </div>
        <div className="record-fig">
          <span className="v">{fmt(profile.follow?.followers ?? 0, 0)}</span>
          <span className="k">followers</span>
        </div>
        <div className="record-fig">
          <span className="v">{fmt(profile.follow?.following ?? 0, 0)}</span>
          <span className="k">following</span>
        </div>
        <div className="record-fig">
          <span className="v">{captures === null ? "—" : fmt(captureCount, 0)}</span>
          <span className="k">captures on the wall</span>
        </div>
      </section>

      {/* the ladder: a rail, rungs on the rail */}
      <section className="record-block">
        <h2 className="record-h">The ladder</h2>
        <p className="record-note">
          Granted by a verified act; levels are not self-declared and do not decay.
        </p>
        <ol className="rail">
          {RUNGS.map((rung) => {
            const isHeld = held.has(rung.key);
            return (
              <li className="rail-step" key={rung.key} data-state={isHeld ? "held" : "not-yet"}>
                <span className="rail-node" aria-hidden="true" />
                <div className="rail-body">
                  <p className="rail-level">{rung.level}</p>
                  <h3 className="rail-name">{rung.name}</h3>
                  <p className="rail-blurb">{rung.blurb}</p>
                  <p className="rail-granted">{isHeld ? rung.granted : "not yet"}</p>
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      {/* the record: what this account put on the wall */}
      <section className="record-block">
        <h2 className="record-h">Captures</h2>
        {captures === null ? (
          <Skeleton rows={1} />
        ) : captureCount === 0 ? (
          <p className="record-note">
            Nothing on the wall under this handle yet. A capture is one number plus the machine it
            came from —{" "}
            <Link href="/submit">file the first one</Link>.
          </p>
        ) : (
          <div className="claim-list">
            {captures.map((claim) => (
              <article className="claim-card" key={claim.id}>
                <div className="claim-top">
                  <Link className="claim-who" href={`/claim/${claim.id}`}>
                    @{claim.claimant_handle}
                  </Link>
                  <span className="status" data-s={claim.status}>
                    {claim.status.replace("_", " ")}
                  </span>
                  <span className="claim-age">{ago(claim.created_at) ?? ""}</span>
                </div>
                <Link className="claim-model" href={`/claim/${claim.id}`}>
                  {claim.model_release_id}
                </Link>
                <div className="claim-num">
                  {claim.claimed_metrics?.decode_tok_s ?? "—"}
                  <small>tok/s decode · claimed</small>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {/* public rigs */}
      <section className="record-block">
        <h2 className="record-h">Public rigs</h2>
        {publicRigs.length === 0 ? (
          <p className="record-note">
            No public rig on this profile. A rig only appears here when its owner marks it public.
          </p>
        ) : (
          <ul className="record-rigs">
            {publicRigs.map((rig) => (
              <li key={rig.slug}>
                <span className="rig-name">{rig.nickname ?? rig.slug}</span>
                <span className="rig-slug">{rig.slug}</span>
                {rig.created_at ? (
                  <span className="rig-age">registered {ago(rig.created_at)}</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
