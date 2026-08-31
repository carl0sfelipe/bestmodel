"use client";

import { FormEvent, useState } from "react";

type Ground = "numbers_unreal" | "wrong_hardware" | "duplicate" | "other";
const grounds: Array<{ value: Ground; label: string }> = [
  { value: "numbers_unreal", label: "Numbers look unrealistic" },
  { value: "wrong_hardware", label: "Hardware does not match" },
  { value: "duplicate", label: "Duplicate submission" },
  { value: "other", label: "Other" },
];

export default function MuralPage() {
  const [open, setOpen] = useState(false);
  const [ground, setGround] = useState<Ground | "">("");
  const [detail, setDetail] = useState("");
  const [evidence, setEvidence] = useState("");
  const [message, setMessage] = useState("");
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ground) return setMessage("Select the grounds for this report.");
    if (ground === "other" && !detail.trim()) return setMessage("Describe the problem: other requires a detail.");
    console.log("[report-unrealistic-run] payload (not transmitted)", { run_id: "sample-preview", reason: ground, detail: detail.trim() || null, evidence_url: evidence.trim() || null });
    setMessage("Payload logged locally. Nothing was transmitted.");
    setOpen(false);
  }
  return <main>
    <span className="sample-tag">SAMPLE · preview data</span>
    <section className="page-head"><p className="kicker">bestmodel.run / mural</p><h1>Every number gets a home<br />and a source.</h1><p>This is a design preview, not an API feed. Every row below is explicitly SAMPLE.</p><div className="actions"><button className="btn primary" type="button" onClick={() => { setMessage(""); setOpen(true); }}>report an unrealistic run</button><a className="btn" href="/console">open production console</a></div>{message && <p className="form-status" role="status">{message}</p>}</section>
    <section aria-label="Sample mural rows">
      <article className="mural-row"><header><span>@rigname</span><span className="sample-badge">SAMPLE</span></header><div className="num">61.4 <small>tok/s decode · Q4_K_M · 8192 ctx</small></div><p>llama.cpp · RTX 3090 · claimed 2026-08-29</p><p className="source-line">source_class: sample_preview · basis: reported</p></article>
      <article className="mural-row"><header><span>@another</span><span className="sample-badge">SAMPLE</span></header><div className="num">47.9 <small>tok/s decode · Q4_K_M · 4096 ctx</small></div><p>llama.cpp · RTX 4070 · settled by Ed25519-signed run</p><p className="source-line">source_class: sample_preview · basis: measured</p></article>
      <article className="mural-row"><header><span>@suspicious</span><span className="sample-badge">SAMPLE</span></header><div className="num">9,999 <small>tok/s decode · Q2_K · 131k ctx</small></div><p>claim refuted - fake caught by the community</p><p className="source-line">source_class: sample_preview · basis: reported</p></article>
    </section>
    <section className="section"><h2>Production today</h2><p className="section-copy">The sample rows above are not data from the API. Real pool cells belong on <a href="/wall">The wall</a>, with their measured or reported basis visible. The report form here is a SAMPLE preview; the real POST remains in the copied console.</p></section>
    {open && <div className="report-scrim" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}><form className="report-panel" onSubmit={submit}><div className="report-head"><div><h2>Report an unrealistic run</h2><span className="source-line">run sample-preview · SAMPLE</span></div><button className="close-button" type="button" aria-label="Close report form" onClick={() => setOpen(false)}>x</button></div><div className="field"><label htmlFor="mural-ground">Grounds</label><select id="mural-ground" value={ground} onChange={(event) => setGround(event.target.value as Ground | "")}><option value="">Select the grounds...</option>{grounds.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div><div className="field"><label htmlFor="mural-detail">Detail</label><textarea id="mural-detail" value={detail} onChange={(event) => setDetail(event.target.value)} placeholder="What is wrong with this run, specifically." /><span className="hint">Required when the grounds are other. Free text otherwise.</span></div><div className="field"><label htmlFor="mural-evidence">Evidence URL</label><input id="mural-evidence" type="url" value={evidence} onChange={(event) => setEvidence(event.target.value)} placeholder="https://..." /><span className="hint">A reproduction, a log, or a competing measurement. Optional.</span></div><div className="report-actions"><button className="btn primary" type="submit">file sample report</button><button className="btn" type="button" onClick={() => setOpen(false)}>cancel</button></div><p className="report-note">No submission endpoint is configured. This preview logs the payload and transmits nothing.</p></form></div>}
  </main>;
}
