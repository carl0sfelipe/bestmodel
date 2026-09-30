import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";

export const metadata = { title: "Transparency", description: "How bestmodel.run makes money, in the open." };

export default async function TransparencyPage() {
  if ((await currentView()) === "agent") {
    return (
      <AgentView>
        {[
          "bestmodel.run / transparency — agent view",
          "",
          "How we make money, in the open",
          "",
          "bestmodel.run is free and ad-free. Two things pay for the GPU and the time:",
          "a cross-promotion the maintainer discloses on every page it appears, and —",
          "someday, if it happens — affiliate links, always labeled.",
          "",
          "Cross-promotion, disclosed",
          "The maintainer of bestmodel.run also owns Orbe Live Imports. When a rig",
          "ranked in the pool (today: the RTX 3090 24GB) is for sale there, /wall",
          "shows a disclosed offer card with a real discount code — never hidden,",
          "never presented as a neutral ranking result.",
          "",
          "Affiliate links — none yet",
          "No affiliate partnership (Mercado Livre, Amazon, KaBuM, or any other) is",
          "active today. If one ever is, every link will carry a visible \"affiliate",
          "link\" label and this page will list exactly what each one paid — same",
          "rule as every number on this site: nothing invented, nothing hidden.",
        ].join("\n")}
      </AgentView>
    );
  }
  return <main><section className="page-head"><p className="kicker">bestmodel.run / transparency</p><h1>How we make money, in the open</h1><p>bestmodel.run is free and ad-free. Two things pay for the GPU and the time: a cross-promotion the maintainer discloses on every page it appears, and — someday, if it happens — affiliate links, always labeled.</p><div className="actions"><a className="btn primary" href="/wall">see the pool -&gt;</a></div></section><section className="section"><h2>Cross-promotion, disclosed</h2><p className="section-copy">The maintainer of bestmodel.run also owns Orbe Live Imports. When a rig ranked in the pool (today: the RTX 3090 24GB) is for sale there, /wall shows a disclosed offer card with a real discount code — never hidden, never presented as a neutral ranking result.</p></section><section className="section"><h2>Affiliate links — none yet</h2><p className="section-copy">No affiliate partnership (Mercado Livre, Amazon, KaBuM, or any other) is active today. If one ever is, every link will carry a visible "affiliate link" label and this page will list exactly what each one paid — same rule as every number on this site: nothing invented, nothing hidden.</p></section></main>;
}
