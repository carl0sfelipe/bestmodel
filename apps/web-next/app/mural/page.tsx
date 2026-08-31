"use client";

import { FormEvent, useMemo, useState } from "react";

/** The five the API accepts (apps/public-api/src/services/create_run_report.py). */
type Ground = "numbers_unreal" | "wrong_hardware" | "wrong_model" | "duplicate" | "other";

const grounds: Array<{ value: Ground; label: string }> = [
  { value: "numbers_unreal", label: "Numbers are not physically possible" },
  { value: "wrong_hardware", label: "Hardware does not match the claim" },
  { value: "wrong_model", label: "Model does not match the claim" },
  { value: "duplicate", label: "Duplicate of an existing claim" },
  { value: "other", label: "Other" },
];

const sampleRows = [
  {
    user: "@rigname",
    num: "61.4",
    meta: "tok/s decode · Q4_K_M · 8192 ctx",
    hardware: "RTX 3090 24GB",
    intent: "chat",
    detail: "llama.cpp · RTX 3090 · claimed 2026-08-29",
    basis: "reported",
  },
  {
    user: "@another",
    num: "47.9",
    meta: "tok/s decode · Q4_K_M · 4096 ctx",
    hardware: "RTX 4070 12GB",
    intent: "code",
    detail: "llama.cpp · RTX 4070 · settled by Ed25519-signed run",
    basis: "measured",
  },
  {
    user: "@suspicious",
    num: "9,999",
    meta: "tok/s decode · Q2_K · 131k ctx",
    hardware: "RTX 3090 24GB",
    intent: "chat",
    detail: "claim refuted - fake caught by the community",
    basis: "reported",
  },
] as const;

export default function MuralPage() {
  const [open, setOpen] = useState(false);
  const [ground, setGround] = useState<Ground | "">("");
  const [detail, setDetail] = useState("");
  const [evidence, setEvidence] = useState("");
  const [message, setMessage] = useState("");

  // One control per dimension. The intent/hardware CHOICE that used to open
  // this page now belongs to the home page's goal-first selector; here they
  // are only filters over the preview rows.
  const [intent, setIntent] = useState("all");
  const [rig, setRig] = useState("all");

  const rigOptions = useMemo(() => [...new Set(sampleRows.map((row) => row.hardware))], []);
  const intentOptions = useMemo(() => [...new Set(sampleRows.map((row) => row.intent))], []);

  const filteredRows = sampleRows.filter(
    (row) => (intent === "all" || row.intent === intent) && (rig === "all" || row.hardware === rig),
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ground) return setMessage("Select the grounds for this report.");
    if (ground === "other" && !detail.trim())
      return setMessage("Describe the problem: other requires a detail.");
    console.log("[report-unrealistic-run] payload (not transmitted)", {
      run_id: "sample-preview",
      reason_category: ground,
      reason_detail: detail.trim() || null,
      evidence_url: evidence.trim() || null,
    });
    setMessage("Payload logged locally. Nothing was transmitted.");
    setOpen(false);
  }

  return (
    <main>
      <section className="page-head">
        <p className="kicker">bestmodel.run / mural</p>
        <h1>The feed, in preview.</h1>
        <p>
          A design preview of the capture feed, not an API read. Every row below is explicitly
          SAMPLE. The live wall is at <a href="/claims">/claims</a>; the entry question — what you
          want to run, and on which machine — lives on the <a href="/">home page</a>.
        </p>
        <p className="sample-tag-inline">SAMPLE · preview data</p>
      </section>

      <section aria-label="Filter the preview rows">
        <div className="ctl-bar">
          <div className="ctl-group">
            <label className="ctl-label" htmlFor="mural-intent">
              intent
            </label>
            <select
              id="mural-intent"
              className="select"
              value={intent}
              onChange={(event) => setIntent(event.target.value)}
            >
              <option value="all">all intents</option>
              {intentOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>

          <div className="ctl-group">
            <label className="ctl-label" htmlFor="mural-rig">
              hardware
            </label>
            <select
              id="mural-rig"
              className="select"
              value={rig}
              onChange={(event) => setRig(event.target.value)}
            >
              <option value="all">all hardware</option>
              {rigOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>

          <div className="ctl-group">
            <span className="ctl-label">report</span>
            <button
              className="btn"
              type="button"
              onClick={() => {
                setMessage("");
                setOpen(true);
              }}
            >
              ⚑ Report a run
            </button>
          </div>
        </div>
        {message && (
          <p className="form-status" role="status">
            {message}
          </p>
        )}
      </section>

      <section aria-label="Sample mural rows">
        {filteredRows.length === 0 ? (
          <p className="note">No sample row matches this filter.</p>
        ) : (
          filteredRows.map((row) => (
            <article className="mural-row" key={row.user}>
              <header>
                <span>{row.user}</span>
                <span className="sample-badge">SAMPLE</span>
              </header>
              <div className="num">
                {row.num} <small>{row.meta}</small>
              </div>
              <p>{row.detail}</p>
              <p className="source-line">
                source_class: sample_preview · basis: {row.basis} · {row.hardware}
              </p>
            </article>
          ))
        )}
      </section>

      <section className="section">
        <h2>Production today</h2>
        <p className="section-copy">
          The sample rows above are not data from the API. Real captured claims belong on{" "}
          <a href="/claims">the wall</a>, and real pool cells on <a href="/wall">the pool</a>, each
          with its measured or reported basis visible. The report form here is a SAMPLE preview; the
          real POST is wired on the claim detail page.
        </p>
      </section>

      {open && (
        <div
          className="report-scrim"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setOpen(false);
          }}
        >
          <form className="report-panel" onSubmit={submit}>
            <div className="report-head">
              <div>
                <h2>Report an unrealistic run</h2>
                <span className="source-line">run sample-preview · SAMPLE</span>
              </div>
              <button
                className="close-button"
                type="button"
                aria-label="Close report form"
                onClick={() => setOpen(false)}
              >
                ✕
              </button>
            </div>

            <div className="field">
              <label htmlFor="mural-ground">Grounds</label>
              <select
                id="mural-ground"
                value={ground}
                onChange={(event) => setGround(event.target.value as Ground | "")}
              >
                <option value="">Select the grounds...</option>
                {grounds.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor="mural-detail">Detail</label>
              <textarea
                id="mural-detail"
                value={detail}
                maxLength={1000}
                onChange={(event) => setDetail(event.target.value)}
                placeholder="What is wrong with this run, specifically."
              />
              <span className="hint">Required when the grounds are other. Max 1000 characters.</span>
            </div>

            <div className="field">
              <label htmlFor="mural-evidence">Evidence URL</label>
              <input
                id="mural-evidence"
                type="url"
                value={evidence}
                onChange={(event) => setEvidence(event.target.value)}
                placeholder="https://..."
              />
              <span className="hint">
                A reproduction, a log, or a competing measurement. Optional.
              </span>
            </div>

            <div className="report-actions">
              <button className="btn primary" type="submit">
                File sample report
              </button>
              <button className="btn" type="button" onClick={() => setOpen(false)}>
                Cancel
              </button>
            </div>
            <p className="report-note">
              No submission endpoint is configured here. This preview logs the payload and transmits
              nothing.
            </p>
          </form>
        </div>
      )}
    </main>
  );
}
