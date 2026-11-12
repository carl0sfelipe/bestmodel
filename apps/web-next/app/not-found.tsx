import Link from "next/link";

// A 404 that still knows where it is: the site map, in one column, with the
// honesty ladder intact. Next's default error page is not this site's voice.
export default function NotFound() {
  return (
    <main>
      <section className="page-head">
        <p className="kicker">404</p>
        <h1>No page at this address.</h1>
        <p>
          Nothing is served here. If you followed a link to a run, a model or a profile, it is
          either gone or was never here — the pool keeps its own truth about what exists.
        </p>
        <div className="actions">
          <Link className="btn primary" href="/">
            back to the workbench
          </Link>
          <Link className="btn" href="/claims">
            the wall
          </Link>
          <Link className="btn" href="/wall">
            the pool
          </Link>
          <Link className="btn" href="/console">
            console
          </Link>
        </div>
      </section>
    </main>
  );
}
