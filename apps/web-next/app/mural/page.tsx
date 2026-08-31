"use client";

import { FormEvent, useState } from "react";

type Ground = "numbers_unreal" | "wrong_hardware" | "duplicate" | "other";
const grounds: Array<{ value: Ground; label: string }> = [
  { value: "numbers_unreal", label: "Numbers look unrealistic" },
  { value: "wrong_hardware", label: "Hardware does not match" },
  { value: "duplicate", label: "Duplicate submission" },
  { value: "other", label: "Other" },
];

const intents = [
  { id: "chat", name: "Chat", icon: "▭", desc: "text generation · chat · reasoning", enabled: true },
  { id: "code", name: "Code", icon: "<", desc: "code completion · reasoning", enabled: true },
  { id: "image", name: "Image gen", icon: "▦", desc: "text → image · diffusion", enabled: false },
  { id: "audio", name: "Audio", icon: "∿", desc: "speech-to-text · text-to-speech", enabled: false },
  { id: "video", name: "Video", icon: "▶", desc: "video generation · animation", enabled: false },
  { id: "vision", name: "Vision", icon: "◉", desc: "image understanding · VLMs", enabled: false },
] as const;

const topRigs = [
  { key: "rtx-3090-24gb", label: "RTX 3090 24GB", runCount: 629 },
  { key: "rtx-3060-12gb-x2", label: "RTX 3060 12GB ×2", runCount: 561 },
  { key: "rtx-3060-12gb", label: "RTX 3060 12GB", runCount: 541 },
  { key: "arc-pro-b70-32gb", label: "Arc Pro B70 32GB", runCount: 328 },
  { key: "rtx-5090-32gb", label: "RTX 5090 32GB", runCount: 303 },
  { key: "ryzen-ai-max-395-128gb", label: "Ryzen AI Max 395 128GB", runCount: 295 },
  { key: "radeon-ai-pro-r9700-32gb-x3", label: "Radeon AI Pro R9700 32GB ×3", runCount: 275 },
  { key: "rtx-4070-12gb", label: "RTX 4070 12GB", runCount: 221 },
] as const;

const sampleRows = [
  { user: "@rigname", num: "61.4", meta: "tok/s decode · Q4_K_M · 8192 ctx", hardware: "RTX 3090 24GB", intent: "chat", detail: "llama.cpp · RTX 3090 · claimed 2026-08-29", basis: "reported" },
  { user: "@another", num: "47.9", meta: "tok/s decode · Q4_K_M · 4096 ctx", hardware: "RTX 4070 12GB", intent: "code", detail: "llama.cpp · RTX 4070 · settled by Ed25519-signed run", basis: "measured" },
  { user: "@suspicious", num: "9,999", meta: "tok/s decode · Q2_K · 131k ctx", hardware: "RTX 3090 24GB", intent: "chat", detail: "claim refuted - fake caught by the community", basis: "reported" },
] as const;

export default function MuralPage() {
  const [open, setOpen] = useState(false);
  const [ground, setGround] = useState<Ground | "">("");
  const [detail, setDetail] = useState("");
  const [evidence, setEvidence] = useState("");
  const [message, setMessage] = useState("");
  const [intent, setIntent] = useState<string | null>(null);
  const [rig, setRig] = useState<string | null>(null);
  const filteredRows = sampleRows.filter((row) => (!intent || row.intent === intent) && (!rig || row.hardware === rig));
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
     <section className="journeys" aria-label="Choose a mural journey">
       <div className="journey-door"><div className="journey-heading"><span className="journey-number">01</span><div><h2>Choose your intent</h2><p>Start from what you want to do. Chat and Code have data today.</p></div></div><div className="intent-grid">{intents.map((item) => <button key={item.id} className={`intent-card${intent === item.id ? " selected" : ""}`} type="button" disabled={!item.enabled} onClick={() => setIntent(intent === item.id ? null : item.id)}><span className="intent-icon" aria-hidden="true">{item.icon}</span><span><strong>{item.name}</strong><small>{item.desc}</small>{!item.enabled && <em>disabled · no data yet</em>}</span></button>)}</div></div>
       <div className="journey-door"><div className="journey-heading"><span className="journey-number">02</span><div><h2>Choose your hardware</h2><p>Start from a rig. This choice is independent from intent.</p></div></div><div className="rig-list">{topRigs.map((item) => <button key={item.key} className={`rig-option${rig === item.label ? " selected" : ""}`} type="button" onClick={() => setRig(rig === item.label ? null : item.label)}><span>{item.label}</span><small>{item.runCount} runs</small></button>)}</div></div>
     </section>
     <section aria-label="Sample mural rows">{filteredRows.map((row) => <article className="mural-row" key={row.user}><header><span>{row.user}</span><span className="sample-badge">SAMPLE</span></header><div className="num">{row.num} <small>{row.meta}</small></div><p>{row.detail}</p><p className="source-line">source_class: sample_preview · basis: {row.basis}</p></article>)}</section>
    <section className="section"><h2>Production today</h2><p className="section-copy">The sample rows above are not data from the API. Real pool cells belong on <a href="/wall">The wall</a>, with their measured or reported basis visible. The report form here is a SAMPLE preview; the real POST remains in the copied console.</p></section>
    {open && <div className="report-scrim" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}><form className="report-panel" onSubmit={submit}><div className="report-head"><div><h2>Report an unrealistic run</h2><span className="source-line">run sample-preview · SAMPLE</span></div><button className="close-button" type="button" aria-label="Close report form" onClick={() => setOpen(false)}>x</button></div><div className="field"><label htmlFor="mural-ground">Grounds</label><select id="mural-ground" value={ground} onChange={(event) => setGround(event.target.value as Ground | "")}><option value="">Select the grounds...</option>{grounds.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div><div className="field"><label htmlFor="mural-detail">Detail</label><textarea id="mural-detail" value={detail} onChange={(event) => setDetail(event.target.value)} placeholder="What is wrong with this run, specifically." /><span className="hint">Required when the grounds are other. Free text otherwise.</span></div><div className="field"><label htmlFor="mural-evidence">Evidence URL</label><input id="mural-evidence" type="url" value={evidence} onChange={(event) => setEvidence(event.target.value)} placeholder="https://..." /><span className="hint">A reproduction, a log, or a competing measurement. Optional.</span></div><div className="report-actions"><button className="btn primary" type="submit">file sample report</button><button className="btn" type="button" onClick={() => setOpen(false)}>cancel</button></div><p className="report-note">No submission endpoint is configured. This preview logs the payload and transmits nothing.</p></form></div>}
  </main>;
}
