import { loadDerived } from "../../lib/engine";
import SubmitClient, { type ModelOption } from "./submit-client";

export const metadata = {
  title: "Capture",
  description:
    "Capture a benchmark number you found in the wild, or report one you measured yourself. Every claim keeps its source.",
};

export default function SubmitPage() {
  // Built on the server so the 212 KB model index never reaches the browser —
  // only the fields the select actually renders travel.
  const options: ModelOption[] = loadDerived()
    .models.map((model) => ({
      id: model.hfId,
      label: model.displayName ?? model.slug,
      category: model.category,
      runCount: model.runCount ?? 0,
    }))
    .sort((a, b) => b.runCount - a.runCount || a.label.localeCompare(b.label));

  return <SubmitClient options={options} />;
}
