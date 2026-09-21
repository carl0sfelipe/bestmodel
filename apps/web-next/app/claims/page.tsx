import Link from "next/link";
import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";
import ClaimsClient from "./claims-client";

export const metadata = {
  title: "The wall",
  description:
    "Every benchmark number captured from the wild, shown with the source it came from, the community's verdict, and what the measured pool says.",
};

export default async function ClaimsPage() {
  if ((await currentView()) === "agent") {
    return (
      <AgentView>
        {[
          "bestmodel.run / the wall (claims feed) — agent view",
          "",
          "Every benchmark number captured from the wild keeps its source link,",
          "collects community verdicts, and can be settled for good by an",
          "Ed25519-signed run. Honesty ladder: measured > reported > extrapolated",
          "> formula > no data yet.",
          "",
          "This page is a live client over the REST API; the numbers are never",
          "rendered server-side here. Agent surface, same data:",
          "  GET /v1/claims?scope=global&sort=recent|controversial|strongest[&status=]",
          "  GET /v1/claims/{id}            claim with prior snapshot and tally",
          "  GET /v1/feed?scope=following   personalized typed feed (auth)",
          "  POST /v1/claims/{id}/votes     { verdict: plausible | impossible } (auth)",
          "  measured pool (static):        /wall?as=agent",
          "",
          "Full contract: /llms.txt · capture flow: /submit?as=agent",
        ].join("\n")}
      </AgentView>
    );
  }
  return (
    <main>
      <section className="feed-head">
        <h1>Claims from the wild</h1>
        <p className="feed-frame">
          benchmark numbers captured from Reddit, X, GitHub and blog posts — each one keeps the
          link it came from, collects community verdicts, and can be settled by an
          Ed25519-signed run ·{" "}
          <Link href="/submit">capture one</Link> · <Link href="/wall">the measured pool</Link>
        </p>
      </section>

      <ClaimsClient />
    </main>
  );
}
