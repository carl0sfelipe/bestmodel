// Presentational pieces shared by the wall and the claim detail.
// Pure — no fetching, no state. Every one of them renders nothing when the
// API did not supply the field, which is how "no invented numbers" is
// enforced structurally rather than by discipline alone.

import Link from "next/link";
import {
  ago,
  contextLabel,
  hostOf,
  mibToGb,
  STATUS_LABEL,
  type Claim,
  type ClaimStatus,
  type ClaimedMetrics,
  type Tally,
} from "../lib/social";

export function fmt(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function StatusBadge({ status }: { status: ClaimStatus }) {
  const label = STATUS_LABEL[status];
  if (!label) return null;
  return (
    <span className="status" data-s={status}>
      {label}
    </span>
  );
}

/**
 * The provenance chip — the hero of the wall.
 * A number found in the wild keeps the link it came from. A self-reported one
 * says so plainly rather than borrowing credibility it has not earned.
 */
export function SourceChip({ claim }: { claim: Claim }) {
  const host = hostOf(claim.source_url);

  if (claim.source_url && host) {
    return (
      <a
        className="src"
        href={claim.source_url}
        target="_blank"
        rel="noopener noreferrer nofollow ugc"
        title={claim.source_url}
      >
        <span>found on</span>
        <span className="host">{host}</span>
        <span className="arw" aria-hidden="true">
          ↗
        </span>
      </a>
    );
  }

  if (claim.source === "localmaxxing") {
    return (
      <span className="src plain">
        imported from localmaxxing{claim.external_ref ? ` · ${claim.external_ref}` : ""}
      </span>
    );
  }

  return <span className="src plain">self-reported · no external source</span>;
}

export function Claimant({ claim }: { claim: Claim }) {
  // Only a claim with a claimant_id has an account behind it. Imports carry a
  // descriptive handle instead, which is rendered as the label it is.
  if (!claim.claimant_id) {
    return (
      <span className="claim-who imported">{claim.claimant_handle ?? "pool import"}</span>
    );
  }
  return (
    <Link className="claim-who" href={`/profile/${encodeURIComponent(claim.claimant_handle ?? "")}`}>
      @{claim.claimant_handle}
    </Link>
  );
}

/**
 * What the measured pool already says, printed beside the claim and never
 * folded into it. The basis string comes from the API; it is not recomputed.
 */
export function CrossSignal({ claim }: { claim: Claim }) {
  const pool = claim.prior_snapshot?.pool;
  const roofline = claim.prior_snapshot?.roofline;
  const hasPool = pool?.p50_decode_tok_s != null;
  const hasRoofline = roofline?.expected_decode_tok_s != null;
  if (!hasPool && !hasRoofline) return null;

  return (
    <div className="cross">
      {hasPool && (
        <div>
          <span className="lbl">engine says: </span>
          <span className={`badge basis-${pool?.basis ?? "reported"}`}>{pool?.basis ?? "unstated"}</span>{" "}
          <b>{fmt(pool?.p50_decode_tok_s)} tok/s</b> median on this class of rig
          {pool?.run_count != null ? ` · n=${pool.run_count}` : ""}
        </div>
      )}
      {hasRoofline && (
        <div>
          <span className="lbl">roofline: </span>
          <span className="badge">formula</span> <b>{fmt(roofline?.expected_decode_tok_s)} tok/s</b>{" "}
          expected ceiling
        </div>
      )}
    </div>
  );
}

export function TallyBar({ tally }: { tally: Tally }) {
  const plausible = Number(tally?.plausible_count ?? 0);
  const impossible = Number(tally?.impossible_count ?? 0);
  const total = plausible + impossible;

  if (!total) {
    return (
      <div className="tally">
        <div className="tally-legend">
          <span>no votes yet</span>
        </div>
      </div>
    );
  }

  return (
    <div className="tally">
      <div
        className="tally-bar"
        role="img"
        aria-label={`${plausible} plausible, ${impossible} impossible`}
      >
        <i className="yes" style={{ width: `${(plausible / total) * 100}%` }} />
        <i className="no" style={{ width: `${(impossible / total) * 100}%` }} />
      </div>
      <div className="tally-legend">
        <span className="yes">{plausible} plausible</span>
        <span className="no">{impossible} impossible</span>
        {tally?.voter_count != null && <span>{tally.voter_count} voters</span>}
        {tally?.margin != null && <span>margin {fmt(tally.margin, 0)}</span>}
      </div>
    </div>
  );
}

export function ClaimMetrics({ metrics }: { metrics: ClaimedMetrics | null }) {
  if (!metrics) return null;
  const vramGb = mibToGb(metrics.peak_vram_mib);
  const parts: React.ReactNode[] = [];

  if (metrics.prefill_tok_s != null)
    parts.push(
      <span key="prefill">
        <span className="k">prefill </span>
        {fmt(metrics.prefill_tok_s, 0)} tok/s
      </span>,
    );
  if (metrics.ttft_ms != null)
    parts.push(
      <span key="ttft">
        <span className="k">ttft </span>
        {fmt(metrics.ttft_ms, 0)} ms
      </span>,
    );
  if (vramGb != null)
    parts.push(
      <span key="vram">
        <span className="k">peak </span>
        {fmt(vramGb)} GB
      </span>,
    );

  if (!parts.length) return null;
  return <div className="claim-metrics">{parts}</div>;
}

/** Only the identifiers the API actually sent. An absent id renders nothing. */
export function ClaimMeta({ claim }: { claim: Claim }) {
  const bits = [
    claim.quantization_profile_id,
    claim.gpu_model_id,
    contextLabel(claim.context_tokens),
  ].filter(Boolean) as string[];
  if (!bits.length) return null;
  return <div className="claim-meta">{bits.join(" · ")}</div>;
}

export function EmptyState({
  mark = "[ ]",
  title,
  body,
  action,
}: {
  mark?: string;
  title: string;
  body?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark" aria-hidden="true">
        {mark}
      </div>
      <h2>{title}</h2>
      {body && <p>{body}</p>}
      {action && <div className="actions">{action}</div>}
    </div>
  );
}

export function Banner({
  kind,
  children,
}: {
  kind: "ok" | "bad" | "note";
  children: React.ReactNode;
}) {
  return (
    <div className="banner" data-k={kind} role={kind === "bad" ? "alert" : "status"}>
      {children}
    </div>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skel" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div className="skel-row" key={i} />
      ))}
    </div>
  );
}

/** One row on the wall. The card link is stretched so the source chip stays live. */
export function ClaimCard({ claim, modelName }: { claim: Claim; modelName: string }) {
  const decode = claim.claimed_metrics?.decode_tok_s;
  const age = ago(claim.created_at);

  return (
    <article className="claim-card">
      <div className="claim-top">
        <Claimant claim={claim} />
        <StatusBadge status={claim.status} />
        {age && (
          <span className="claim-age" title={claim.created_at}>
            {age}
          </span>
        )}
      </div>

      <Link className="claim-model" href={`/claim/${encodeURIComponent(claim.id)}`}>
        {modelName}
      </Link>

      {decode != null ? (
        <div className="claim-num">
          {fmt(decode)}
          <small>tok/s decode</small>
        </div>
      ) : (
        <div className="claim-num absent">no decode rate claimed</div>
      )}

      <ClaimMetrics metrics={claim.claimed_metrics} />
      <ClaimMeta claim={claim} />
      {claim.note && <p className="claim-note">{claim.note}</p>}

      <SourceChip claim={claim} />
      <CrossSignal claim={claim} />
      <TallyBar tally={claim.tally} />
    </article>
  );
}
