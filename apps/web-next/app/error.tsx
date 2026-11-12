"use client";

// A server-rendered page that throws renders this. It says what happened in
// the site's own voice and offers the way back — never a stack trace.
export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <main>
      <section className="page-head">
        <p className="kicker">error</p>
        <h1>This page could not be assembled.</h1>
        <p>
          The request reached the site and the site could not answer it. Nothing was changed and
          nothing was lost — try the same page again.
        </p>
        <div className="actions">
          <button className="btn primary" type="button" onClick={() => reset()}>
            try again
          </button>
          <a className="btn" href="/">
            back to the workbench
          </a>
        </div>
      </section>
    </main>
  );
}
