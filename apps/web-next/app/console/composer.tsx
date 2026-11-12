"use client";

import { useState } from "react";

import {
  createPost,
  MAX_POST_BODY,
  POST_KINDS,
  type PostKind,
} from "../../lib/social";

/**
 * The composer. A post carries text only — the API refuses a body that
 * smuggles in metrics, and the copy says so before anybody tries.
 */
export default function Composer({ onPosted }: { onPosted: () => void }) {
  const [body, setBody] = useState("");
  const [kind, setKind] = useState<PostKind>("note");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [problem, setProblem] = useState(false);

  async function submit() {
    const text = body.trim();
    if (!text) {
      setProblem(true);
      setMessage("Write something first.");
      return;
    }
    setBusy(true);
    setMessage(null);
    const result = await createPost({ body: text, kind });
    setBusy(false);
    if (!result.ok) {
      setProblem(true);
      setMessage(result.detail ?? "The post could not be sent.");
      return;
    }
    setProblem(false);
    setBody("");
    setMessage("Posted.");
    onPosted();
  }

  const remaining = MAX_POST_BODY - body.length;

  return (
    <section className="composer" aria-label="Write a post">
      <div className="ctl-group">
        <span className="ctl-label">kind</span>
        <div className="opt-row" role="group" aria-label="Post kind">
          {POST_KINDS.map((option) => (
            <button
              key={option.value}
              type="button"
              className="opt"
              aria-pressed={kind === option.value}
              onClick={() => setKind(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label htmlFor="composer-body">post</label>
        <textarea
          id="composer-body"
          value={body}
          maxLength={MAX_POST_BODY}
          onChange={(event) => setBody(event.target.value)}
          placeholder="What did you measure, what did you see, what do you want to know?"
        />
        <span className={`help${remaining < 40 ? " err" : ""}`}>
          Text only. A number belongs in a claim — post the claim, not the number.
        </span>
      </div>

      <div className="desk-actions">
        <button className="btn primary" type="button" disabled={busy} onClick={() => void submit()}>
          {busy ? "sending…" : "Post"}
        </button>
        {message && (
          <p className={problem ? "help err" : "form-status"} role="status">
            {message}
          </p>
        )}
      </div>
    </section>
  );
}
