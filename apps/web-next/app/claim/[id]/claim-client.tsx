"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Banner,
  Claimant,
  CrossSignal,
  EmptyState,
  Skeleton,
  SourceChip,
  StatusBadge,
  TallyBar,
  fmt,
} from "../../../components/claim-parts";
import {
  ago,
  contextLabel,
  CONSOLE_HREF,
  getClaim,
  getToken,
  MAX_REASON_DETAIL,
  mibToGb,
  REASON_CATEGORIES,
  reportClaim,
  voteOnClaim,
  type Claim,
  type ReasonCategory,
  type Verdict,
} from "../../../lib/social";

type Phase = "idle" | "sending" | "done" | "error";

export default function ClaimClient({ id }: { id: string }) {
  const [claim, setClaim] = useState<Claim | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<{ status: number; detail: string } | null>(null);
  const [signedIn, setSignedIn] = useState(false);

  // The token only exists in the browser, so this is read after mount to keep
  // the server and first client render identical.
  useEffect(() => setSignedIn(getToken() != null), []);

  const refresh = useCallback(async () => {
    const result = await getClaim(id);
    if (result.ok && result.data) {
      setClaim(result.data);
      setLoadError(null);
    } else {
      setLoadError({ status: result.status, detail: result.detail ?? "Unknown error." });
    }
    setLoading(false);
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (loading) {
    return (
      <main>
        <section className="page-head">
          <p className="kicker">bestmodel.run / claim</p>
        </section>
        <Skeleton rows={2} />
      </main>
    );
  }

  if (loadError?.status === 404) {
    return (
      <main>
        <section className="page-head">
          <p className="kicker">bestmodel.run / claim</p>
        </section>
        <EmptyState
          mark="404"
          title="No such claim."
          body="This id does not match anything on the wall. It may have been retracted, or the link may be wrong."
          action={
            <Link className="btn primary" href="/claims">
              Back to the wall
            </Link>
          }
        />
      </main>
    );
  }

  if (!claim) {
    return (
      <main>
        <section className="page-head">
          <p className="kicker">bestmodel.run / claim</p>
        </section>
        <Banner kind="bad">
          <b>this claim could not be loaded</b> — {loadError?.detail}
        </Banner>
      </main>
    );
  }

  const metrics = claim.claimed_metrics;
  const vramGb = mibToGb(metrics?.peak_vram_mib);
  const age = ago(claim.created_at);

  return (
    <main>
      <section className="page-head">
        <p className="kicker">bestmodel.run / claim</p>
        <h1>{claim.model_release_id}</h1>
        <div className="claim-top" style={{ marginTop: 16 }}>
          <Claimant claim={claim} />
          <StatusBadge status={claim.status} />
          {age && <span className="claim-age" title={claim.created_at}>{age}</span>}
        </div>
      </section>

      {claim.status === "settled_verified" && (
        <Banner kind="ok">
          <b>verified by signed run</b>
          {claim.benchmark_run_id ? ` — run ${claim.benchmark_run_id.slice(0, 8)}` : ""}. The number
          below stopped being a claim and became a measurement.
        </Banner>
      )}
      {claim.status === "refuted" && (
        <Banner kind="bad">
          <b>refuted</b> — the community found this claim unreal and the report was credited.
        </Banner>
      )}
      {claim.status === "retracted" && (
        <Banner kind="note">
          <b>retracted</b> — the claimant withdrew this claim. It stays visible so the record is
          complete.
        </Banner>
      )}

      {/* the claimed numbers, large and monospaced */}
      <section className="panel">
        <p className="panel-t">claimed</p>
        <div className="figs">
          <div className="fig">
            <span className={metrics?.decode_tok_s == null ? "v none" : "v"}>
              {metrics?.decode_tok_s == null ? "not claimed" : fmt(metrics.decode_tok_s)}
            </span>
            <span className="k">tok/s decode</span>
          </div>
          <div className="fig">
            <span className={metrics?.prefill_tok_s == null ? "v none" : "v"}>
              {metrics?.prefill_tok_s == null ? "not claimed" : fmt(metrics.prefill_tok_s, 0)}
            </span>
            <span className="k">tok/s prefill</span>
          </div>
          <div className="fig">
            <span className={metrics?.ttft_ms == null ? "v none" : "v"}>
              {metrics?.ttft_ms == null ? "not claimed" : fmt(metrics.ttft_ms, 0)}
            </span>
            <span className="k">ms to first token</span>
          </div>
          <div className="fig">
            <span className={vramGb == null ? "v none" : "v"}>
              {vramGb == null ? "not claimed" : `${fmt(vramGb)} GB`}
            </span>
            <span className="k">peak vram</span>
          </div>
        </div>
      </section>

      {/* where it came from */}
      <section className="panel">
        <p className="panel-t">the origin</p>
        <SourceChip claim={claim} />
        <dl className="defs" style={{ marginTop: 18 }}>
          <div>
            <dt>model</dt>
            <dd>{claim.model_release_id}</dd>
          </div>
          {claim.quantization_profile_id && (
            <div>
              <dt>quantization</dt>
              <dd>{claim.quantization_profile_id}</dd>
            </div>
          )}
          {claim.gpu_model_id && (
            <div>
              <dt>hardware</dt>
              <dd>{claim.gpu_model_id}</dd>
            </div>
          )}
          {contextLabel(claim.context_tokens) && (
            <div>
              <dt>context</dt>
              <dd>{contextLabel(claim.context_tokens)}</dd>
            </div>
          )}
          {claim.note && (
            <div>
              <dt>note</dt>
              <dd>{claim.note}</dd>
            </div>
          )}
        </dl>
        <CrossSignal claim={claim} />
      </section>

      <VotePanel claim={claim} signedIn={signedIn} onVoted={refresh} />

      {claim.status === "open" && <SettlePanel id={claim.id} />}

      <ReportPanel claim={claim} signedIn={signedIn} />

      <div className="actions">
        <Link className="btn" href="/claims">
          Back to the wall
        </Link>
      </div>
    </main>
  );
}

/* ------------------------------------------------------------------ votes */

function VotePanel({
  claim,
  signedIn,
  onVoted,
}: {
  claim: Claim;
  signedIn: boolean;
  onVoted: () => Promise<void>;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState<Verdict | null>(null);

  async function cast(verdict: Verdict) {
    setPending(verdict);
    setPhase("sending");
    setMessage(null);

    const result = await voteOnClaim(claim.id, verdict);
    setPending(null);

    if (result.ok) {
      setPhase("done");
      setMessage("Vote recorded.");
      await onVoted();
      return;
    }
    // 409 is the API telling you something real (self-vote, already voted);
    // its wording is better than anything invented here.
    setPhase("error");
    setMessage(result.detail);
  }

  return (
    <section className="panel">
      <p className="panel-t">community verdict</p>
      <TallyBar tally={claim.tally} />

      {!signedIn ? (
        <div className="actions">
          <Link className="btn primary" href={CONSOLE_HREF}>
            Sign in to vote
          </Link>
        </div>
      ) : (
        <>
          <div className="actions">
            <button
              type="button"
              className="btn"
              disabled={phase === "sending"}
              onClick={() => void cast("plausible")}
            >
              {pending === "plausible" ? "Sending…" : "Plausible"}
            </button>
            <button
              type="button"
              className="btn bad"
              disabled={phase === "sending"}
              onClick={() => void cast("impossible")}
            >
              {pending === "impossible" ? "Sending…" : "Impossible"}
            </button>
          </div>
          {message && (
            <p className={phase === "error" ? "note" : "form-status"} role="status">
              {message}
            </p>
          )}
        </>
      )}
      <p className="note">
        A vote is a reading, not a proof. Only a signed run settles a claim.
      </p>
    </section>
  );
}

/* ----------------------------------------------------------------- settle */

function SettlePanel({ id }: { id: string }) {
  const command = `benchmark-probe upload --settle-claim ${id}`;
  const [copied, setCopied] = useState<"idle" | "ok" | "fail">("idle");

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied("ok");
      setTimeout(() => setCopied("idle"), 2000);
    } catch {
      setCopied("fail");
    }
  }

  return (
    <section className="panel">
      <p className="panel-t">prove it with a signed run</p>
      <p className="section-copy" style={{ marginBottom: 16 }}>
        Run the same workload on the same class of machine and upload the result. A validated
        Ed25519-signed run settles this claim for everyone, permanently.
      </p>
      <div className="cmd">
        <span className="p" aria-hidden="true">
          $
        </span>
        <code>{command}</code>
        <button type="button" className="btn ghost" onClick={() => void copy()}>
          {copied === "ok" ? "Copied" : copied === "fail" ? "Copy failed" : "Copy"}
        </button>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- report */

function ReportPanel({ claim, signedIn }: { claim: Claim; signedIn: boolean }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [category, setCategory] = useState<ReasonCategory | "">("");
  const [detail, setDetail] = useState("");
  const [touched, setTouched] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const categoryError = touched && !category ? "Pick the grounds for this report." : null;
  const detailError =
    touched && detail.length > MAX_REASON_DETAIL
      ? `Too long by ${detail.length - MAX_REASON_DETAIL} characters.`
      : null;

  function open() {
    setPhase("idle");
    setMessage(null);
    setTouched(false);
    dialogRef.current?.showModal();
  }

  function close() {
    dialogRef.current?.close();
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!category || detail.length > MAX_REASON_DETAIL) return;

    setPhase("sending");
    setMessage(null);
    const result = await reportClaim(claim.id, category, detail.trim());

    if (result.ok) {
      setPhase("done");
      setMessage("Report filed. If it is confirmed, that is a fake caught — +5 points.");
      return;
    }
    setPhase("error");
    setMessage(result.detail);
  }

  return (
    <section className="panel">
      <p className="panel-t">something wrong with this claim?</p>
      <p className="section-copy" style={{ marginBottom: 16 }}>
        Reports are how the pool stays honest. A confirmed fake caught is worth{" "}
        <strong>+5 points</strong> to the reporter.
      </p>

      {signedIn ? (
        <button type="button" className="btn" onClick={open}>
          ⚑ Report this claim
        </button>
      ) : (
        <Link className="btn" href={CONSOLE_HREF}>
          Sign in to report
        </Link>
      )}

      <dialog className="modal" ref={dialogRef} onClose={close}>
        <div className="modal-body">
          <div className="modal-top">
            <div>
              <h2>Report this claim</h2>
              <p className="source-line">claim {claim.id.slice(0, 8)}</p>
            </div>
            <button type="button" className="modal-x" aria-label="Close report form" onClick={close}>
              ✕
            </button>
          </div>

          {phase === "done" ? (
            <>
              <Banner kind="ok">{message}</Banner>
              <div className="actions">
                <button type="button" className="btn" onClick={close}>
                  Close
                </button>
              </div>
            </>
          ) : (
            <form className="form" onSubmit={submit} noValidate>
              <div className="f">
                <label htmlFor="report-category">
                  Grounds<span className="r">required</span>
                </label>
                <select
                  id="report-category"
                  value={category}
                  aria-invalid={categoryError ? "true" : undefined}
                  aria-describedby="report-category-help"
                  onBlur={() => setTouched(true)}
                  onChange={(event) => setCategory(event.target.value as ReasonCategory | "")}
                >
                  <option value="">Select the grounds…</option>
                  {REASON_CATEGORIES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <span id="report-category-help" className={categoryError ? "help err" : "help"}>
                  {categoryError ?? "What exactly is wrong with it."}
                </span>
              </div>

              <div className="f">
                <label htmlFor="report-detail">
                  Detail<span className="o">optional</span>
                </label>
                <textarea
                  id="report-detail"
                  value={detail}
                  maxLength={MAX_REASON_DETAIL + 200}
                  aria-invalid={detailError ? "true" : undefined}
                  aria-describedby="report-detail-help"
                  placeholder="This rig tops out near 40 tok/s at this quant."
                  onBlur={() => setTouched(true)}
                  onChange={(event) => setDetail(event.target.value)}
                />
                <span id="report-detail-help" className={detailError ? "help err" : "help"}>
                  {detailError ?? `${detail.length} / ${MAX_REASON_DETAIL} characters.`}
                </span>
              </div>

              {phase === "error" && message && <Banner kind="bad">{message}</Banner>}

              <div className="actions">
                <button type="submit" className="btn primary" disabled={phase === "sending"}>
                  {phase === "sending" ? "Filing…" : "File report"}
                </button>
                <button type="button" className="btn" onClick={close}>
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      </dialog>
    </section>
  );
}
