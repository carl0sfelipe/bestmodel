import { currentView } from "../../../lib/view-server";
import AgentView from "../../_components/agent-view";
import ClaimClient from "./claim-client";

export const metadata = {
  title: "Claim",
  description:
    "A captured benchmark claim: the number, where it was found, what the measured pool says, and how the community voted.",
};

export default async function ClaimPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if ((await currentView()) === "agent") {
    return (
      <AgentView>
        {[
          `bestmodel.run / claim — ${id} (agent view)`,
          "",
          "A captured benchmark claim: the number, the source it came from, what",
          "the measured pool says (prior snapshot), and the community verdict.",
          "This page is a live client; the record itself is the machine surface:",
          "",
          `  GET /v1/claims/${id}    claim, prior snapshot, tally, status`,
          "  POST /v1/claims/{id}/votes   { verdict: plausible | impossible } (auth)",
          "",
          "Honesty ladder: measured > reported > extrapolated > formula > no data yet.",
        ].join("\n")}
      </AgentView>
    );
  }
  return <ClaimClient id={id} />;
}
