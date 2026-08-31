import { loadDerived } from "../../lib/engine";
import SubmitClient, { type ModelLabel } from "./submit-client";

export const metadata = {
  title: "Capture",
  description:
    "Capture a benchmark number you found in the wild, or report one you measured yourself. Every claim keeps its source.",
};

export default function SubmitPage() {
  // Labels only. The VALUES the form submits come from the API's own catalog —
  // the derived index is used solely to put a readable name on an opaque id,
  // and never to invent one.
  const labels: ModelLabel[] = loadDerived().models.map((model) => ({
    slug: model.slug,
    name: model.displayName ?? model.slug,
    category: model.category,
  }));

  return <SubmitClient labels={labels} />;
}
