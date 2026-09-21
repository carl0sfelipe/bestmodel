import { loadDerived } from "../../lib/engine";
import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";
import SubmitClient, { type ModelLabel } from "./submit-client";

export const metadata = {
  title: "Capture",
  description:
    "Capture a benchmark number you found in the wild, or report one you measured yourself. Every claim keeps its source.",
};

export default async function SubmitPage() {
  // Labels only. The VALUES the form submits come from the API's own catalog
  // (see submit-client): create_run_claim 404s on any model_release_id it
  // cannot resolve, and hfId is not one of them. The derived index is used
  // solely to put a readable name on an opaque id, never to invent one — so
  // multimodal rows without an hfId are carried here on slug alone.
  const labels: ModelLabel[] = loadDerived().models.map((model) => ({
    slug: model.slug,
    name: model.displayName ?? model.slug,
    category: model.category,
  }));

  if ((await currentView()) === "agent") {
    return (
      <AgentView>
        {[
          "bestmodel.run / capture — agent view",
          "",
          "Two honest doors, zero trust on arrival:",
          "  1. claim a run you witnessed or found in the wild (keeps its source url);",
          "     the community votes, then an Ed25519-signed run settles it for good.",
          "  2. measure it yourself: benchmark-probe signs and uploads a validated run",
          "     (getting-started: /cli?as=agent).",
          "",
          "Machine surface:",
          "  POST /v1/claims        { model_release_id, claimed_metrics, source_url? } (auth)",
          "  console:               /console (passkey, same loop without a terminal)",
          "",
          `Model ids the catalog resolves today (${labels.length}):`,
          ...labels.map((label) => `  ${label.slug} (${label.category})`),
        ].join("\n")}
      </AgentView>
    );
  }

  return <SubmitClient labels={labels} />;
}
