import { formatNumber, loadDerived } from "../../lib/engine";
import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";
import HardwareIndex from "./hardware-index";
import "./hardware.css";

export const metadata = {
  title: "Hardware",
  description: "A catalogue of the machines the pool has actually been run on, ordered by the load each one carried.",
};

export default async function HardwarePage() {
  const { hardware, pool, stats } = loadDerived();
  const snapshotAt = stats.snapshotAt.slice(0, 10);

  if ((await currentView()) === "agent") {
    const byRig = new Map<string, { cells: number; models: Set<string> }>();
    for (const cell of pool) {
      const bucket = byRig.get(cell.rigKey) ?? { cells: 0, models: new Set<string>() };
      bucket.cells += 1;
      bucket.models.add(cell.modelSlug);
      byRig.set(cell.rigKey, bucket);
    }
    const lines = [...hardware]
      .sort((a, b) => (b.runCount ?? 0) - (a.runCount ?? 0))
      .map((rig) => {
        const bucket = byRig.get(rig.key);
        return [
          `  ${rig.label.padEnd(40)}`,
          rig.key.padEnd(36),
          `${String(rig.runCount ?? 0).padStart(5)} runs`,
          `${String(rig.memGb ?? 0).padStart(6)} GB`,
          `${rig.gpuCount} GPU`,
          rig.bandwidthGBs == null ? "bw unstated" : `${formatNumber(rig.bandwidthGBs)} GB/s`,
          bucket ? `${bucket.models.size} models` : "0 models",
        ].join(" | ");
      });
    return (
      <AgentView>
        {[
          "bestmodel.run / hardware — agent view",
          "",
          `Machines the pool has run on, ordered by runs. Snapshot ${snapshotAt}.`,
          "Opening a rig filters the measured pool: /wall?rig=<key>&as=agent.",
          "",
          "  label | key | runs | memory | gpus | bandwidth | models tried",
          ...lines,
        ].join("\n")}
      </AgentView>
    );
  }

  const busiest = hardware.reduce((top, rig) => ((rig.runCount ?? 0) > (top.runCount ?? 0) ? rig : top), hardware[0]);

  return (
    <main>
      <section className="page-head hw-head">
        <p className="kicker">bestmodel.run / hardware</p>
        <h1>Every machine the pool has run on</h1>
        <p>
          A catalogue of the hardware under test, ordered by the load each machine actually carried.
          Runs come from the frozen snapshot; models tried are counted from the pool cells that cite
          the rig. Open a machine to see its cells on the Wall.
        </p>
        <div className="figs hw-figs-top">
          <div className="fig">
            <span className="v">{formatNumber(hardware.length, 0)}</span>
            <span className="k">machines listed</span>
          </div>
          <div className="fig">
            <span className="v">{formatNumber(busiest.runCount, 0)}</span>
            <span className="k">runs on the busiest machine</span>
          </div>
          <div className="fig">
            <span className="v">{formatNumber(pool.length, 0)}</span>
            <span className="k">pool cells behind the counts</span>
          </div>
          <div className="fig">
            <span className="v">{snapshotAt}</span>
            <span className="k">snapshot date</span>
          </div>
        </div>
      </section>

      <HardwareIndex snapshotAt={snapshotAt} />

      <section className="section hw-note">
        <p className="section-copy">
          The catalogue is a snapshot, not a live throughput reading. A machine with a low run count
          is under-tested, not slow. Bandwidth is stated only where the submitter reported it.
        </p>
      </section>
    </main>
  );
}
