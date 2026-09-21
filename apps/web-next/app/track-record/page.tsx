import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";

export const metadata = { title: "Track record", description: "A trust ladder granted by verified acts." };

export default async function TrackRecordPage() {
  if ((await currentView()) === "agent") {
    return (
      <AgentView>
        {[
          "bestmodel.run / track record — agent view",
          "",
          "Trust is a ladder climbed by verified acts, never self-declared, and",
          "every act is attributable to an Ed25519 key. Levels:",
          "  01 contributor  granted by: a validated signed run",
          "  02 replicator   granted by: validated reproductions",
          "                  (threshold: proposal - dial pending owner)",
          "  03 auditor      granted by: confirmed fake caught + reproductions",
          "                  (threshold: proposal - dial pending owner)",
          "",
          "Scoring:",
          "  validated signed run              x2  live",
          "  confirmed fake caught             x5  live",
          "  reproduction of another's run     x3  proposed (lands with the flow)",
        ].join("\n")}
      </AgentView>
    );
  }
  return <main><section className="page-head"><p className="kicker">bestmodel.run / track record</p><h1>Trust is a ladder,<br />climbed by verified acts.</h1><p>Each level is granted by a verified act, never self-declared, and does not decay. Every act is attributable to an Ed25519 key.</p><div className="actions"><a className="btn primary" href="/console">start contributing -&gt;</a></div></section><section className="card-grid"><article className="card"><small className="kicker">level 01</small><h3>Contributor</h3><p>You run benchmarks on your own hardware and submit signed results. One machine, one voice, but a real one on the record.</p><p className="basis-measured">granted by: a validated signed run</p></article><article className="card"><small className="kicker">level 02</small><h3>Replicator</h3><p>You independently reproduce other contributors' runs, confirming or contradicting reported numbers.</p><p className="basis-measured">granted by: validated reproductions</p><span className="note">threshold: proposal - dial pending owner</span></article><article className="card"><small className="kicker">level 03</small><h3>Auditor</h3><p>You defend the pool: replicate high-impact cells and report unreal runs through moderation.</p><p className="basis-measured">granted by: confirmed fake caught + reproductions</p><span className="note">threshold: proposal - dial pending owner</span></article></section><section className="section"><h2>Scoring</h2><div className="table-wrap"><table><tbody><tr><td>validated signed run</td><td className="basis-measured">×2 · live</td></tr><tr><td>confirmed fake caught</td><td className="basis-measured">×5 · live</td></tr><tr><td>reproduction of another contributor's run</td><td>×3 · proposed</td></tr></tbody></table></div><p className="note">The ×3 reproduction reward is marked proposal; it lands with the reproduce flow.</p></section></main>; }
