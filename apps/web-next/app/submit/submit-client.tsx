"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Banner } from "../../components/claim-parts";
import {
  CONSOLE_HREF,
  createClaim,
  FIELD_MAX,
  getToken,
  isHttpUrl,
  type Claim,
  type CreateClaimBody,
} from "../../lib/social";

export type ModelOption = { id: string; label: string; category: string; runCount: number };

/** The two doors. Which one you walk through changes what the form requires. */
type Journey = "found" | "ran";

export default function SubmitClient({ options }: { options: ModelOption[] }) {
  const [signedIn, setSignedIn] = useState(false);
  const [journey, setJourney] = useState<Journey | null>(null);

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

  useEffect(() => setSignedIn(getToken() != null), []);

  const grouped = useMemo(() => {
    const byCategory = new Map<string, ModelOption[]>();
    for (const option of options) {
      const list = byCategory.get(option.category) ?? [];
      list.push(option);
      byCategory.set(option.category, list);
    }
    return [...byCategory.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [options]);

  const sourceRequired = journey === "found";
  const decodeValue = Number(decode);

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
    if (quant.trim()) body.quantization_profile_id = quant.trim();
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
      <main>
        <section className="page-head">
          <p className="kicker">bestmodel.run / capture</p>
          <h1>Captured.</h1>
          <p>The number now has a home, a source, and a path to proof.</p>
        </section>
        <section className="panel">
          <p className="panel-t">your claim</p>
          <div className="claim-num">
            {created.claimed_metrics?.decode_tok_s ?? "—"}
            <small>tok/s decode</small>
          </div>
          <div className="claim-meta">{created.model_release_id}</div>
          <div className="actions">
            <Link className="btn primary" href={`/claim/${encodeURIComponent(created.id)}`}>
              Open the claim
            </Link>
            <Link className="btn" href="/claims">
              Back to the wall
            </Link>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main>
      <section className="page-head">
        <p className="kicker">bestmodel.run / capture</p>
        <h1>
          Bring the number in
          <br />
          from the wild.
        </h1>
        <p>
          Two ways in, and they are not the same claim. One is something you saw someone else post;
          the other is something you ran. Pick the honest one.
        </p>
      </section>

      {/* OWNER'S LAW: two doors, side by side. Never one selector with a
          toggle buried inside it. */}
      <div className="doors">
        <button
          type="button"
          className="door"
          aria-pressed={journey === "found"}
          onClick={() => setJourney("found")}
        >
          <span className="door-n">01</span>
          <h2>I found it online</h2>
          <p>
            A number in a Reddit thread, an X post, a GitHub issue, a blog benchmark. You are
            capturing someone else&apos;s claim, so it must carry its link.
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
            it — your note is the context.
          </p>
          <span className="req">source url optional</span>
        </button>
      </div>

      {journey === null ? (
        <p className="note">Pick a door to open the capture form.</p>
      ) : !signedIn ? (
        <>
          <Banner kind="note">
            <b>sign in required</b> — the console issues your session token. The form below stays
            disabled until you have one, because a claim without an attributable author is exactly
            the problem this wall exists to fix.
          </Banner>
          <div className="actions">
            <Link className="btn primary" href={CONSOLE_HREF}>
              Sign in to capture
            </Link>
          </div>
          <CaptureForm
            disabled
            journey={journey}
            grouped={grouped}
            values={{ modelId, decode, sourceUrl, quant, gpu, context, note }}
            errors={{}}
            setters={{}}
            onSubmit={() => {}}
            sending={false}
          />
        </>
      ) : (
        <>
          {apiError && (
            <Banner kind="bad">
              <b>the claim was not created</b> — {apiError}
            </Banner>
          )}
          <CaptureForm
            journey={journey}
            grouped={grouped}
            values={{ modelId, decode, sourceUrl, quant, gpu, context, note }}
            errors={{ modelError, decodeError, sourceError, contextError }}
            setters={{
              setModelId,
              setDecode,
              setSourceUrl,
              setQuant,
              setGpu,
              setContext,
              setNote,
              setTouched,
            }}
            onSubmit={submit}
            sending={sending}
            blocked={touched && blocked}
          />
        </>
      )}
    </main>
  );
}

type Values = {
  modelId: string;
  decode: string;
  sourceUrl: string;
  quant: string;
  gpu: string;
  context: string;
  note: string;
};

type Errors = {
  modelError?: string | null;
  decodeError?: string | null;
  sourceError?: string | null;
  contextError?: string | null;
};

type Setters = {
  setModelId?: (v: string) => void;
  setDecode?: (v: string) => void;
  setSourceUrl?: (v: string) => void;
  setQuant?: (v: string) => void;
  setGpu?: (v: string) => void;
  setContext?: (v: string) => void;
  setNote?: (v: string) => void;
  setTouched?: (v: boolean) => void;
};

function CaptureForm({
  journey,
  grouped,
  values,
  errors,
  setters,
  onSubmit,
  sending,
  disabled = false,
  blocked = false,
}: {
  journey: Journey;
  grouped: [string, ModelOption[]][];
  values: Values;
  errors: Errors;
  setters: Setters;
  onSubmit: (event: React.FormEvent) => void;
  sending: boolean;
  disabled?: boolean;
  blocked?: boolean;
}) {
  const touch = () => setters.setTouched?.(true);
  const sourceRequired = journey === "found";

  return (
    <form className="form" onSubmit={onSubmit} noValidate>
      {/* UX LAW: model, machine, quantization and context are separate
          controls. They are never collapsed into one dropdown. */}
      <div className="f">
        <label htmlFor="cap-model">
          Model<span className="r">required</span>
        </label>
        <select
          id="cap-model"
          value={values.modelId}
          disabled={disabled}
          aria-invalid={errors.modelError ? "true" : undefined}
          aria-describedby="cap-model-help"
          onBlur={touch}
          onChange={(event) => setters.setModelId?.(event.target.value)}
        >
          <option value="">Select a model…</option>
          {grouped.map(([category, list]) => (
            <optgroup key={category} label={category}>
              {list.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                  {option.runCount ? ` · ${option.runCount} runs` : ""}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <span id="cap-model-help" className={errors.modelError ? "help err" : "help"}>
          {errors.modelError ?? "Grouped by modality. Only text models have pool data today."}
        </span>
      </div>

      <div className="f">
        <label htmlFor="cap-source">
          Source URL
          {sourceRequired ? <span className="r">required</span> : <span className="o">optional</span>}
        </label>
        <input
          id="cap-source"
          type="url"
          inputMode="url"
          value={values.sourceUrl}
          disabled={disabled}
          maxLength={FIELD_MAX.source_url}
          placeholder="https://reddit.com/r/LocalLLaMA/…"
          aria-invalid={errors.sourceError ? "true" : undefined}
          aria-describedby="cap-source-help"
          onBlur={touch}
          onChange={(event) => setters.setSourceUrl?.(event.target.value)}
        />
        <span id="cap-source-help" className={errors.sourceError ? "help err" : "help"}>
          {errors.sourceError ??
            (sourceRequired
              ? "Where the number was posted. This is what makes it verifiable by anyone."
              : "Add one if the run is also posted somewhere public.")}
        </span>
      </div>

      <div className="f">
        <label htmlFor="cap-decode">
          Decode rate<span className="r">required</span>
        </label>
        <input
          id="cap-decode"
          type="number"
          inputMode="decimal"
          step="0.01"
          min="0"
          value={values.decode}
          disabled={disabled}
          placeholder="41.5"
          aria-invalid={errors.decodeError ? "true" : undefined}
          aria-describedby="cap-decode-help"
          onBlur={touch}
          onChange={(event) => setters.setDecode?.(event.target.value)}
        />
        <span id="cap-decode-help" className={errors.decodeError ? "help err" : "help"}>
          {errors.decodeError ?? "tok/s during generation — the headline number of the claim."}
        </span>
      </div>

      <div className="form-grid">
        <div className="f">
          <label htmlFor="cap-quant">
            Quantization<span className="o">optional</span>
          </label>
          <input
            id="cap-quant"
            value={values.quant}
            disabled={disabled}
            maxLength={FIELD_MAX.quantization_profile_id}
            placeholder="Q4_K_M"
            onChange={(event) => setters.setQuant?.(event.target.value)}
          />
          <span className="help">The quant profile as the source stated it.</span>
        </div>

        <div className="f">
          <label htmlFor="cap-gpu">
            Hardware<span className="o">optional</span>
          </label>
          <input
            id="cap-gpu"
            value={values.gpu}
            disabled={disabled}
            maxLength={FIELD_MAX.gpu_model_id}
            placeholder="RTX 3090 24GB"
            onChange={(event) => setters.setGpu?.(event.target.value)}
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
            value={values.context}
            disabled={disabled}
            placeholder="32768"
            aria-invalid={errors.contextError ? "true" : undefined}
            aria-describedby="cap-context-help"
            onBlur={touch}
            onChange={(event) => setters.setContext?.(event.target.value)}
          />
          <span id="cap-context-help" className={errors.contextError ? "help err" : "help"}>
            {errors.contextError ?? "Tokens of context the run used."}
          </span>
        </div>
      </div>

      <div className="f">
        <label htmlFor="cap-note">
          Note<span className="o">optional</span>
        </label>
        <textarea
          id="cap-note"
          value={values.note}
          disabled={disabled}
          maxLength={FIELD_MAX.note}
          placeholder={
            journey === "found"
              ? "What the poster said around the number."
              : "Engine, flags, anything that would let someone reproduce this."
          }
          onChange={(event) => setters.setNote?.(event.target.value)}
        />
        <span className="help">Context a reader would need to judge the claim.</span>
      </div>

      <div className="actions">
        <button
          type="submit"
          className="btn primary"
          disabled={disabled || sending}
          aria-disabled={disabled ? "true" : undefined}
        >
          {sending ? "Capturing…" : "Capture this run"}
        </button>
      </div>
      {blocked && (
        <p className="help err" role="status">
          Fix the fields marked above, then capture.
        </p>
      )}
    </form>
  );
}
