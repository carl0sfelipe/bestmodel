import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";
import {
  CALIBRATION_ANCHORS, GPUS, MODELS, MTP_ACCEPT, U_BW, USABLE_MEM,
  parsePlanQuery, plan, type Band, type PlanRow,
} from "../../lib/rig-planner";

export const metadata = {
  title: "Planejar rig alugado",
  description: "Quantos tok/s você tira de um modelo num hardware que ainda não tem medição no pool: estimativa modelada, com faixa, por quantização e contexto.",
};

const CTX_OPTIONS = [32_768, 131_072, 212_000, 524_288, 1_048_576];
const band = (b: Band | null) => (b ? `${b.mid} (${b.low}–${b.high})` : "-");

function agentText(rows: PlanRow[], label: string, ctx: number) {
  return [
    `bestmodel.run / planejar — agent view`,
    `rig: ${label} · context ${ctx} tokens · basis: modeled (NOT measured)`,
    "",
    "model           quant         fits  need/usable GB   tok/s mid (low-high)   +MTP mid (low-high)   TTFT s",
    ...rows.map((r) =>
      `${r.model.label.padEnd(15)} ${r.quant.label.padEnd(13).slice(0, 13)} ${(r.fits ? "yes" : "no").padEnd(5)} ${`${r.needGb}/${r.usableGb}`.padEnd(16)} ${band(r.tokS).padEnd(22)} ${band(r.tokSWithMtp).padEnd(21)} ${r.ttftS ?? "-"}`),
    "",
    "Method: t_step = active weight bytes / (BW x 0.75 x GPUs) + KV read / BW + layers x per-layer cost.",
    "Per-layer cost band fitted on pool cells; see /blog/glm-5-3-vs-flash-4x-b300.",
  ].join("\n");
}

export default async function PlanejarPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const query = parsePlanQuery(await searchParams);
  const gpu = GPUS[query.gpu];
  const rows = plan(query);
  const rigLabel = `${query.gpus}× ${gpu.label}`;

  if ((await currentView()) === "agent") return <AgentView>{agentText(rows, rigLabel, query.contextTokens)}</AgentView>;

  // The verdict compares the quant people actually serve with: FP8.
  const pick = (m: string) => rows.find((r) => r.model.key === m && r.quant.key === "fp8" && r.tokS);
  const full = pick("glm-5.3"), flash = pick("glm-5.3-flash");

  return (
    <main>
      <section className="page-head">
        <p className="kicker">bestmodel.run / planejar</p>
        <h1>Quantos tok/s você tira do rig antes de alugar</h1>
        <p>Nenhum contribuidor mediu este rig ainda, então o número abaixo é <strong>modelado</strong>, não medido: física de banda de memória mais um custo fixo por camada calibrado em medições reais do pool. Cada valor vem com faixa.</p>
        <form className="toolbar" method="get">
          <label><span className="ctl-label">GPU</span>
            <select className="select" name="gpu" defaultValue={query.gpu}>
              {Object.values(GPUS).map((g) => <option key={g.key} value={g.key}>{g.label}</option>)}
            </select></label>
          <label><span className="ctl-label">Quantidade</span>
            <select className="select" name="n" defaultValue={String(query.gpus)}>
              {[1, 2, 4, 8].map((n) => <option key={n} value={n}>{n}×</option>)}
            </select></label>
          <label><span className="ctl-label">Contexto</span>
            <select className="select" name="ctx" defaultValue={String(query.contextTokens)}>
              {CTX_OPTIONS.map((c) => <option key={c} value={c}>{Math.round(c / 1000)}k</option>)}
            </select></label>
          <button className="btn primary" type="submit">recalcular</button>
        </form>
      </section>

      {full && flash ? (
        <section className="verdict">
          <p className="overline">{rigLabel} · {Math.round(query.contextTokens / 1000)}k de contexto · 1 usuário</p>
          <p className="verdict-num">{flash.tokS!.mid}<small>tok/s Flash ({flash.quant.label})</small></p>
          <p className="verdict-num">{full.tokS!.mid}<small>tok/s GLM-5.3 cheio ({full.quant.label})</small></p>
          <p className="verdict-meta">Flash ≈ {(flash.tokS!.mid / full.tokS!.mid).toFixed(1)}× mais rápido · base: modeled · sem MTP</p>
        </section>
      ) : null}

      <section className="section">
        <h2>Por <em>quantização</em></h2>
        <div className="table-wrap"><table>
          <thead><tr><th>Modelo</th><th>Quant · engine</th><th>Cabe?</th><th>Memória (GB)</th><th>tok/s</th><th>tok/s com MTP</th><th>TTFT</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.model.key + r.quant.key}>
              <td>{r.model.label}</td>
              <td>{r.quant.label} · {r.quant.engine}</td>
              <td className={r.fits ? "basis-measured" : "basis-reported"}>{r.fits ? "sim" : "não"}</td>
              <td>{r.needGb} / {r.usableGb}</td>
              <td>{band(r.tokS)}</td>
              <td>{band(r.tokSWithMtp)}</td>
              <td>{r.ttftS == null ? "-" : `${r.ttftS} s`}</td>
            </tr>))}
          </tbody>
        </table></div>
        <p className="note">tok/s = mid (low–high), decode com 1 usuário. MTP assume aceite de {MTP_ACCEPT.low}–{MTP_ACCEPT.high} tokens por passo. TTFT = prefill do contexto inteiro, MFU 40%. Memória usável = {Math.round(USABLE_MEM * 100)}% por GPU; banda efetiva = {Math.round(U_BW * 100)}% da nominal.</p>
      </section>

      <section className="section">
        <h2>De onde vem o <em>número</em></h2>
        <p className="section-copy">Em batch 1 cada token lê os pesos ativos uma vez, mas em rigs multi-GPU o que domina é o custo fixo por camada (kernels, all-reduce, roteamento MoE). Por isso o Flash, com 45 camadas contra 78, ganha bem menos que a razão 40B/18B de parâmetros ativos sugere. A atenção esparsa (DSA) deixa o contexto quase irrelevante para o decode; ele pesa no TTFT.</p>
        <div className="table-wrap"><table>
          <thead><tr><th>Âncora do pool</th><th>Medido</th></tr></thead>
          <tbody>{CALIBRATION_ANCHORS.map((a) => <tr key={a.cell}><td>{a.what}</td><td>{a.measuredTokS} tok/s</td></tr>)}</tbody>
        </table></div>
        <p className="note">Specs: {Object.values(MODELS).map((m) => m.source).join(" · ")} · {gpu.source}</p>
        <div className="actions"><a className="btn primary" href="/console">alugou? meça e envie -&gt;</a> <a className="btn" href="/blog/glm-5-3-vs-flash-4x-b300">leia a análise</a></div>
      </section>
    </main>
  );
}
