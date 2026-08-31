import { Suspense } from "react";
import WallClient from "./wall-client";

export const metadata = { title: "The wall", description: "Every community benchmark cell with its provenance: measured or reported." };

export default function WallPage() {
  return <main><section className="page-head"><p className="kicker">bestmodel.run / the wall</p><h1>What the community<br />actually measures.</h1><p>Every row is a real cell from the community pool. Cells carry their run count and their basis, and ranking is provisional.</p><div className="actions"><a className="btn primary" href="/console">capture or correct a number -&gt;</a></div></section><Suspense fallback={<p className="summary">reading the pool...</p>}><WallClient /></Suspense></main>;
}
