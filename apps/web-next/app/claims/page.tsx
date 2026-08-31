import Link from "next/link";
import ClaimsClient from "./claims-client";

export const metadata = {
  title: "The wall",
  description:
    "Every benchmark number captured from the wild, shown with the source it came from, the community's verdict, and what the measured pool says.",
};

export default function ClaimsPage() {
  return (
    <main>
      <section className="page-head">
        <p className="kicker">bestmodel.run / the wall</p>
        <h1>
          Every number gets a home
          <br />
          and a source.
        </h1>
        <p>
          Benchmark claims live scattered across Reddit, X, GitHub and blog posts — numbers with
          nobody behind them. Captured here, each one keeps the link it came from, collects
          community verdicts, and can be settled for good by an Ed25519-signed run.
        </p>
        <div className="actions">
          <Link className="btn primary" href="/submit">
            Capture a run
          </Link>
          <Link className="btn" href="/wall">
            Browse the measured pool
          </Link>
        </div>
      </section>

      <ClaimsClient />
    </main>
  );
}
