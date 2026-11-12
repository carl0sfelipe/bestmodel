"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Banner,
  CrossSignal,
  SourceChip,
  StatusBadge,
  TallyBar,
} from "../../components/claim-parts";
import { fetchSession, type SessionInfo } from "../../lib/auth";
import {
  CONSOLE_HREF,
  createClaim,
  fetchCatalog,
  FIELD_MAX,
  getToken,
  hostOf,
  isHttpUrl,
  listClaims,
  voteOnClaim,
  type Claim,
  type CreateClaimBody,
  type ModelRelease,
  type QuantizationProfile,
} from "../../lib/social";

export type ModelLabel = { slug: string; name: string; category: string };

/** The two doors. Which one you walk through changes what the form requires. */
type Journey = "found" | "ran";

type Option = { id: string; label: string; category: string };

/**
 * The tier ceilings the API enforces, copied from the server's own policy
 * table (apps/public-api/src/services/rate_limit_policy.py). The API is the
 * authority: it counts the claims in the window and refuses past the ceiling,
 * and its 429 states the number it used. This table is printed so the caller
 * can read their standing before they file, not to replace the check.
 */
const CLAIM_CEILING: ReadonlyArray<[string, number]> = [
  ["L0", 2],
  ["L1", 5],
  ["L2", 10],
  ["L3", 25],
  ["L4", 50],
];

/**
 * Put a readable name on an opaque server id without ever changing the id.
 * `model-qwen3-6-35b-a3b` is matched against the derived slug
 * `qwen-qwen3-6-35b-a3b`; on no confident match the raw id is the label.
 */
function decorate(id: string, labels: ModelLabel[]): Option {
  const stem = id.replace(/^model-/, "");
  const hit =
    labels.find((l) => l.slug === stem) ??
    labels.find((l) => l.slug.endsWith(`-${stem}`)) ??
    labels.find((l) => l.slug.endsWith(stem));
  return { id, label: hit?.name ?? id, category: hit?.category ?? "other" };
}

export default function SubmitClient({ labels }: { labels: ModelLabel[] }) {
  const [signedIn, setSignedIn] = useState(false);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [journey, setJourney] = useState<Journey | null>(null);

  const [catalog, setCatalog] = useState<
    | { source: "api"; models: ModelRelease[]; quants: QuantizationProfile[] }
    | { source: "feed"; models: string[]; quants: string[] }
    | null
  >(null);
  const [catalogFailed, setCatalogFailed] = useState(false);

  const [modelId, setModelId] = useState("");
  const [decode, setDecode] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [quant, setQuant] = useState("");
  const [gpu, setGpu] = useState("");
  const [context, setContext] = useState("");
  const [note, setNote] = useState("");

  const [touched, setTouched] = useState(false);
  const [sending, setSending] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [created, setCreated] = useState<Claim | null>(null);

  // Open claims waiting on somebody's judgement. Filing a number is one half
  // of the loop; reading the ones already filed is the other.
  const [openClaims, setOpenClaims] = useState<Claim[] | null>(null);
  const [voted, setVoted] = useState<string | null>(null);
  const [voteError, setVoteError] = useState<string | null>(null);
  const [voting, setVoting] = useState<string | null>(null);

  useEffect(() => setSignedIn(getToken() != null), []);

  // Tier and points come from the API's own session endpoint. Nothing about
  // the caller's standing is guessed from local storage.
  useEffect(() => {
    if (getToken() == null) return;
    let live = true;
    fetchSession().then((info) => {
      if (live) setSession(info);
    });
    return () => {
      live = false;
    };
  }, []);

  const loadOpen = useCallback(async () => {
    const result = await listClaims({ status: "open", sort: "recent", limit: 8, offset: 0 });
    if (result.ok && result.data) setOpenClaims(result.data);
  }, []);

  useEffect(() => {
    void loadOpen();
  }, [loadOpen]);

  useEffect(() => {
    fetchCatalog()
      .then((result) => {
        // Falling back to the feed is degradation, not failure. An EMPTY list
        // is failure either way: the form cannot be completed without a model,
        // so it stays disabled and says so instead of looking usable.
        if (!result.models.length) setCatalogFailed(true);
        setCatalog(result);
      })
      .catch(() => setCatalogFailed(true));
  }, []);

  const grouped = useMemo(() => {
    const byCategory = new Map<string, Option[]>();
    for (const model of catalog?.models ?? []) {
      const option = typeof model === "string" ? decorate(model, labels) : decorate(model.id, labels);
      if (typeof model !== "string") option.label = model.release_name;
      const list = byCategory.get(option.category) ?? [];
      list.push(option);
      byCategory.set(option.category, list);
    }
    for (const list of byCategory.values()) list.sort((a, b) => a.label.localeCompare(b.label));
    return [...byCategory.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [catalog, labels]);

  const quantLabel = useMemo(() => {
    const quants = catalog?.quants ?? [];
    for (const item of quants) {
      const id = typeof item === "string" ? item : item.id;
      if (id === quant) return typeof item === "string" ? item : item.display_name;
    }
    return null;
  }, [catalog, quant]);

  const modelLabel = useMemo(() => {
    for (const [, list] of grouped) {
      const hit = list.find((option) => option.id === modelId);
      if (hit) return hit.label;
    }
    return null;
  }, [grouped, modelId]);

  const sourceRequired = journey === "found";
  const decodeValue = Number(decode);
  const sourceValid = isHttpUrl(sourceUrl.trim());

  const modelError = touched && !modelId ? "Pick the model this number is about." : null;
  const decodeError =
    touched && (!decode.trim() || !Number.isFinite(decodeValue) || decodeValue <= 0)
      ? "A decode rate in tok/s is required — it is the number being claimed."
      : null;
  const sourceError =
    touched && sourceRequired && !isHttpUrl(sourceUrl.trim())
      ? "This journey needs the http(s) link where you found the number."
      : touched && sourceUrl.trim() && !isHttpUrl(sourceUrl.trim())
        ? "That is not a valid http(s) URL."
        : null;
  const contextError =
    touched && context.trim() && !(Number.isFinite(Number(context)) && Number(context) > 0)
      ? "Context must be a positive number of tokens."
      : null;

  const blocked = Boolean(modelError || decodeError || sourceError || contextError);

  // The sheet is inert until there is a session to file under and a catalog to
  // pick model ids from. Both gates are stated on the page, not hidden.
  const disabled = !signedIn || !catalog || catalogFailed;
  const loading = !catalog && !catalogFailed;
  const errors = signedIn ? { modelError, decodeError, sourceError, contextError } : {};
  const touch = () => setTouched(true);
  const quants = catalog?.quants ?? [];
  const catalogSource = catalog?.source ?? null;

  // The caller's ceiling comes from the tier the API reports, looked up in the
  // same policy table the server enforces.
  const tier = session?.reputation?.tier ?? null;
  const claimCeiling = tier
    ? (CLAIM_CEILING.find(([name]) => name === tier)?.[1] ?? CLAIM_CEILING[0][1])
    : "—";

  // What the claim will be, as far as the form can tell. The slip never
  // claims the number is measured: a claim carries the basis it came in with.
  const slipBasis: "sourced" | "self" | "blocked" =
    journey === null
      ? "self"
      : sourceRequired && !sourceValid
        ? "blocked"
        : sourceValid
          ? "sourced"
          : "self";

  async function vote(id: string, verdict: "plausible" | "impossible") {
    setVoting(id);
    setVoteError(null);
    const result = await voteOnClaim(id, verdict);
    setVoting(null);
    if (!result.ok) {
      setVoteError(result.detail);
      return;
    }
    setVoted(id);
    await loadOpen();
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (
      !modelId ||
      !decode.trim() ||
      !Number.isFinite(decodeValue) ||
      decodeValue <= 0 ||
      (sourceRequired && !isHttpUrl(sourceUrl.trim())) ||
      (sourceUrl.trim() && !isHttpUrl(sourceUrl.trim())) ||
      (context.trim() && !(Number.isFinite(Number(context)) && Number(context) > 0))
    ) {
      return;
    }

    const body: CreateClaimBody = {
      model_release_id: modelId,
      claimed_metrics: { decode_tok_s: decodeValue },
    };
    if (sourceUrl.trim()) body.source_url = sourceUrl.trim();
    if (quant) body.quantization_profile_id = quant;
    if (gpu.trim()) body.gpu_model_id = gpu.trim();
    if (context.trim()) body.context_tokens = Number(context);
    if (note.trim()) body.note = note.trim();

    setSending(true);
    setApiError(null);
    const result = await createClaim(body);
    setSending(false);

    if (result.ok && result.data) {
      setCreated(result.data);
      return;
    }
    setApiError(result.detail);
  }

  if (created) {
    return (
      <section className="cap-receipt">
          <p className="kicker">bestmodel.run / capture</p>
          <h2>Filed.</h2>
          <p className="cap-frame">
            The number is on the wall as an open claim with your name on it. It carries the source
            you gave it, or it says it has none.
          </p>

          <div className="panel">
            <p className="panel-t">your claim</p>
            <div className="claim-num">
              {created.claimed_metrics?.decode_tok_s ?? "—"}
              <small>tok/s decode</small>
            </div>
            <div className="claim-top">
              <span className="claim-who">filed under your handle</span>
              <StatusBadge status={created.status} />
            </div>
            <div className="claim-meta">{created.model_release_id}</div>
            <div style={{ marginTop: 12 }}>
              <SourceChip claim={created} />
            </div>
            <CrossSignal claim={created} />
            <TallyBar tally={created.tally} />
          </div>

          <div className="actions">
            <Link className="btn primary" href={`/claim/${encodeURIComponent(created.id)}`}>
              Open the claim
            </Link>
            <Link className="btn" href="/claims">
              Back to the wall
            </Link>
          </div>

          <p className="cap-ladder">
            It stays a claim until somebody with the rig posts a signed run for the same cell. The
            community votes on whether the number is plausible in the meantime; a signed run is
            what settles it.
          </p>
      </section>
    );
  }

  return (
    <>
      {/* The two doors, side by side. The rule they encode: a number found
          somewhere keeps the link it came from; a number you ran is filed as
          self-reported and says so. */}
      <div className="doors">
        <button
          type="button"
          className="door"
          aria-pressed={journey === "found"}
          onClick={() => setJourney("found")}
        >
          <span className="door-n">01</span>
          <h2>I saw it somewhere</h2>
          <p>
            A number in a Reddit thread, an X post, a GitHub issue, a blog benchmark. You are
            capturing someone else&apos;s claim, so it has to carry its link.
          </p>
          <span className="req">source url required</span>
        </button>

        <button
          type="button"
          className="door"
          aria-pressed={journey === "ran"}
          onClick={() => setJourney("ran")}
        >
          <span className="door-n">02</span>
          <h2>I ran it myself</h2>
          <p>
            Your machine, your run. It enters the wall as self-reported until a signed run settles
            it, and your note carries the context.
          </p>
          <span className="req">source url optional</span>
        </button>
      </div>

      {journey === null ? (
        <p className="note">Open a door to start the sheet.</p>
      ) : (
        <>
          <section className="cap-standing" aria-label="Your standing">
            {signedIn ? (
              <>
                <span>
                  signed in as <span className="t">@{session?.handle ?? "…"}</span>
                </span>
                <span>
                  tier <span className="t">{session?.reputation?.tier ?? "—"}</span> ·{" "}
                  {session?.reputation?.points ?? 0} points
                </span>
                <span className="s">
                  claims allowed per 24 h at your tier —{" "}
                  <span className="t">{claimCeiling}</span>
                </span>
              </>
            ) : (
              <span className="s">
                No session on this device. The console issues one, and a claim is filed under the
                handle it belongs to.
              </span>
            )}
            <span className="s">
              ceiling by tier, as the API&apos;s own policy table states it —{" "}
              {CLAIM_CEILING.map(([name, n], index) => (
                <span key={name}>
                  {name} {n}
                  {index === CLAIM_CEILING.length - 1 ? "" : " · "}
                </span>
              ))}
            </span>
            <span className="s">
              the API counts the claims of the last 24 h and refuses past the ceiling, quoting the
              number it used
            </span>
          </section>

          {!signedIn && (
            <>
              <Banner kind="note">
                <b>sign in required</b> — the console issues your session token. The sheet below
                stays disabled until you have one, because a claim without an attributable author is
                exactly the problem this wall exists to fix.
              </Banner>
              <div className="actions">
                <Link className="btn primary" href={CONSOLE_HREF}>
                  Sign in to capture
                </Link>
              </div>
            </>
          )}

          {signedIn && apiError && (
            <Banner kind="bad">
              <b>the claim was not created</b> — {apiError}
            </Banner>
          )}

          {catalogFailed && (
            <Banner kind="bad">
              <b>the model catalog could not be read</b> — the sheet needs the API&apos;s own model
              ids and cannot guess them, so it stays disabled.
            </Banner>
          )}

          <div className="cap-bench">
            <form className="cap-sheet" onSubmit={submit} noValidate>
              <div className="cap-basis" data-b={slipBasis}>
                <span className="b">
                  {slipBasis === "blocked"
                    ? "cannot file yet"
                    : slipBasis === "sourced"
                      ? "keeps its source"
                      : "self-reported"}
                </span>
                <span>
                  {slipBasis === "blocked"
                    ? "A number found somewhere carries the link it came from. Add it and the sheet becomes fileable."
                    : slipBasis === "sourced"
                      ? "The link you give below travels with the claim. Anyone can open it and check the number."
                      : "No link, no borrowed authority. The claim enters the wall marked as yours and unverified."}
                </span>
              </div>

              {/* UX LAW: model, machine, quantization and context are separate
                  controls. They are never collapsed into one dropdown. */}
              <section className="cap-station">
                <div className="cap-station-h">
                  <span className="cap-station-n">01</span>
                  <h2>The model</h2>
                  <span className="req">required</span>
                </div>
                <div className="cap-station-b">
                  <div className="f">
                    <label htmlFor="cap-model">Model</label>
                    <select
                      id="cap-model"
                      value={modelId}
                      disabled={disabled}
                      aria-invalid={errors.modelError ? "true" : undefined}
                      aria-describedby="cap-model-help"
                      onBlur={touch}
                      onChange={(event) => setModelId?.(event.target.value)}
                    >
                      <option value="">
                        {loading ? "reading the catalog…" : "Select a model…"}
                      </option>
                      {grouped.map(([category, list]) => (
                        <optgroup key={category} label={category}>
                          {list.map((option) => (
                            <option key={option.id} value={option.id}>
                              {option.label}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                    <span id="cap-model-help" className={errors.modelError ? "help err" : "help"}>
                      {errors.modelError ??
                        (catalogSource === "api"
                          ? "Grouped by modality. This is the complete API catalog."
                          : "Grouped by modality. The catalog route did not respond, so this lists what the wall has already shown.")}
                    </span>
                  </div>

                  <div className="f">
                    <label htmlFor="cap-quant">
                      Quantization<span className="o">optional</span>
                    </label>
                    <select
                      id="cap-quant"
                      value={quant}
                      disabled={disabled}
                      onChange={(event) => setQuant?.(event.target.value)}
                    >
                      <option value="">not stated</option>
                      {quants.map((quant) => {
                        const id = typeof quant === "string" ? quant : quant.id;
                        const label = typeof quant === "string" ? quant : quant.display_name;
                        return (
                          <option key={id} value={id}>
                            {label}
                          </option>
                        );
                      })}
                    </select>
                    <span className="help">Server profile ids — free text would be rejected.</span>
                  </div>
                </div>
              </section>

              <section className="cap-station">
                <div className="cap-station-h">
                  <span className="cap-station-n">02</span>
                  <h2>The machine</h2>
                  <span className="opt">optional</span>
                </div>
                <div className="cap-station-b">
                  <div className="cap-pair">
                    <div className="f">
                      <label htmlFor="cap-gpu">
                        Hardware<span className="o">optional</span>
                      </label>
                      <input
                        id="cap-gpu"
                        value={gpu}
                        disabled={disabled}
                        maxLength={FIELD_MAX.gpu_model_id}
                        placeholder="RTX 3090 24GB"
                        onChange={(event) => setGpu?.(event.target.value)}
                      />
                      <span className="help">The machine the number was produced on.</span>
                    </div>

                    <div className="f">
                      <label htmlFor="cap-context">
                        Context<span className="o">optional</span>
                      </label>
                      <input
                        id="cap-context"
                        type="number"
                        inputMode="numeric"
                        min="1"
                        step="1"
                        max={FIELD_MAX.context_tokens}
                        value={context}
                        disabled={disabled}
                        placeholder="32768"
                        aria-invalid={errors.contextError ? "true" : undefined}
                        aria-describedby="cap-context-help"
                        onBlur={touch}
                        onChange={(event) => setContext?.(event.target.value)}
                      />
                      <span id="cap-context-help" className={errors.contextError ? "help err" : "help"}>
                        {errors.contextError ?? "Tokens of context the run used."}
                      </span>
                    </div>
                  </div>
                </div>
              </section>

              <section className="cap-station">
                <div className="cap-station-h">
                  <span className="cap-station-n">03</span>
                  <h2>The number</h2>
                  <span className="req">required</span>
                </div>
                <div className="cap-station-b">
                  <div className="f">
                    <label htmlFor="cap-decode">Decode rate</label>
                    <input
                      id="cap-decode"
                      type="number"
                      inputMode="decimal"
                      step="0.01"
                      min="0"
                      value={decode}
                      disabled={disabled}
                      placeholder="41.5"
                      aria-invalid={errors.decodeError ? "true" : undefined}
                      aria-describedby="cap-decode-help"
                      onBlur={touch}
                      onChange={(event) => setDecode?.(event.target.value)}
                    />
                    <span id="cap-decode-help" className={errors.decodeError ? "help err" : "help"}>
                      {errors.decodeError ?? "tok/s during generation — the headline number of the claim."}
                    </span>
                  </div>
                </div>
              </section>

              <section className="cap-station">
                <div className="cap-station-h">
                  <span className="cap-station-n">04</span>
                  <h2>Where it came from</h2>
                  {sourceRequired ? <span className="req">required</span> : <span className="opt">optional</span>}
                </div>
                <div className="cap-station-b">
                  <div className="f">
                    <label htmlFor="cap-source">Source URL</label>
                    <input
                      id="cap-source"
                      type="url"
                      inputMode="url"
                      value={sourceUrl}
                      disabled={disabled}
                      maxLength={FIELD_MAX.source_url}
                      placeholder="https://reddit.com/r/LocalLLaMA/…"
                      aria-invalid={errors.sourceError ? "true" : undefined}
                      aria-describedby="cap-source-help"
                      onBlur={touch}
                      onChange={(event) => setSourceUrl?.(event.target.value)}
                    />
                    <span id="cap-source-help" className={errors.sourceError ? "help err" : "help"}>
                      {errors.sourceError ??
                        (sourceRequired
                          ? "Where the number was posted. This is what makes it verifiable by anyone."
                          : "Add one if the run is also posted somewhere public.")}
                    </span>
                  </div>

                  <div className="f">
                    <label htmlFor="cap-note">
                      Note<span className="o">optional</span>
                    </label>
                    <textarea
                      id="cap-note"
                      value={note}
                      disabled={disabled}
                      maxLength={FIELD_MAX.note}
                      placeholder={
                        journey === "found"
                          ? "What the poster said around the number."
                          : "Engine, flags, anything that would let someone reproduce this."
                      }
                      onChange={(event) => setNote?.(event.target.value)}
                    />
                    <span className="help">Context a reader would need to judge the claim.</span>
                  </div>
                </div>
              </section>

              <div className="cap-sheet-foot">
                <div className="actions">
                  <button
                    type="submit"
                    className="btn primary"
                    disabled={disabled || sending}
                    aria-disabled={disabled ? "true" : undefined}
                  >
                    {sending ? "Filing…" : "File the claim"}
                  </button>
                </div>
                {blocked && (
                  <p className="help err" role="status">
                    Fix the fields marked above, then file.
                  </p>
                )}
              </div>
            </form>

            <aside className="cap-slip" aria-label="What this claim becomes">
              <p className="cap-slip-t">the slip</p>
              <div className={decode.trim() ? "cap-slip-num" : "cap-slip-num empty"}>
                {decode.trim() ? decode.trim() : "—"}
                <small>tok/s decode</small>
              </div>
              <dl className="cap-slip-rows">
                <div>
                  <dt>model</dt>
                  <dd>{modelLabel ?? "—"}</dd>
                </div>
                <div>
                  <dt>quantization</dt>
                  <dd>{quantLabel ?? "not stated"}</dd>
                </div>
                <div>
                  <dt>machine</dt>
                  <dd>{gpu.trim() || "not stated"}</dd>
                </div>
                <div>
                  <dt>context</dt>
                  <dd>{context.trim() ? `${context.trim()} tokens` : "not stated"}</dd>
                </div>
                <div>
                  <dt>source</dt>
                  <dd>
                    {sourceValid
                      ? (hostOf(sourceUrl.trim()) ?? sourceUrl.trim())
                      : journey === "found"
                        ? "required — no link yet"
                        : "none — self-reported"}
                  </dd>
                </div>
                <div>
                  <dt>basis</dt>
                  <dd>
                    reported — {sourceValid ? "asserted, with its link" : "asserted, no link"}
                  </dd>
                </div>
                <div>
                  <dt>status</dt>
                  <dd>open, waiting on a signed run</dd>
                </div>
              </dl>
              <p className="cap-slip-foot">
                A claim is never a measurement. It carries the basis it came in with until a signed
                run settles it.{" "}
                <Link href="/claims">See the wall</Link>
              </p>
            </aside>
          </div>

          <section className="cap-queue" aria-label="Open claims awaiting judgement">
            <p className="cap-slip-t">open claims awaiting judgement</p>
            {openClaims == null ? (
              <p className="note">reading the wall…</p>
            ) : openClaims.length === 0 ? (
              <p className="note">No open claims right now.</p>
            ) : (
              <ul className="cap-queue-list">
                {openClaims.map((row) => (
                  <li key={row.id}>
                    <div className="cap-queue-n">
                      {row.claimed_metrics?.decode_tok_s ?? "—"}
                      <small>tok/s</small>
                    </div>
                    <div className="cap-queue-meta">
                      <span className="cap-queue-model">{row.model_release_id}</span>
                      <span>
                        {row.source_url
                          ? `found on ${hostOf(row.source_url) ?? "a link"}`
                          : "self-reported, no external source"}
                      </span>
                      {row.tally?.voter_count != null ? (
                        <span>{row.tally.voter_count} votes</span>
                      ) : (
                        <span>no votes yet</span>
                      )}
                    </div>
                    <div className="cap-queue-actions">
                      <button
                        type="button"
                        className="btn"
                        disabled={!signedIn || voting === row.id}
                        aria-label={`Vote ${row.model_release_id} plausible`}
                        onClick={() => vote(row.id, "plausible")}
                      >
                        plausible
                      </button>
                      <button
                        type="button"
                        className="btn"
                        disabled={!signedIn || voting === row.id}
                        aria-label={`Vote ${row.model_release_id} impossible`}
                        onClick={() => vote(row.id, "impossible")}
                      >
                        impossible
                      </button>
                      <Link className="btn ghost" href={`/claim/${encodeURIComponent(row.id)}`}>
                        open
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {voteError && (
              <p className="help err" role="status">
                the vote was not counted — {voteError}
              </p>
            )}
            {voted && !voteError && (
              <p className="form-status" role="status">
                Vote counted. It counts with your tier&apos;s weight.
              </p>
            )}
            <p className="cap-slip-foot">
              A vote is a judgement on the number, not a measurement of it. Reporting a claim lives
              on its own page.
              {!signedIn ? " Voting needs a session; the console issues one." : ""}
            </p>
          </section>
        </>
      )}
    </>
  );
}
