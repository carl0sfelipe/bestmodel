import Link from "next/link";
import { formatNumber, topRigs } from "../../lib/engine";

export const metadata = { title: "Hardware", description: "Browse reference rigs ordered by community run count." };

export default function HardwarePage() {
  return <main><section className="page-head"><p className="kicker">bestmodel.run / hardware</p><h1>Reference rigs,<br />with a real track record.</h1><p>Pick a rig to open the Wall with that hardware pre-selected. The pool only shows what has actually been submitted.</p></section><section className="hardware-grid">{topRigs().map((rig) => <Link className="hardware-card" key={rig.key} href={`/wall?rig=${encodeURIComponent(rig.key)}`}><h2>{rig.label}</h2><p><strong>{formatNumber(rig.runCount, 0)}</strong> runs</p><p>{rig.memGb} GB · {rig.hwClass} · {rig.gpuCount} GPU{rig.gpuCount === 1 ? "" : "s"}</p><p>{rig.bandwidthGBs == null ? "bandwidth unstated" : `${formatNumber(rig.bandwidthGBs)} GB/s`}</p></Link>)}</section></main>;
}
