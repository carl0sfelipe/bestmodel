import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";
import "./track-record.css";

export const metadata = {
  title: "Track record",
  description: "A trust ladder granted by verified acts.",
};

type StepState = "live" | "not-yet" | "proposed";

/**
 * The ladder, frozen. Each step names the act that grants it, what the pool
 * records when that act happens, what the step carries, and the state of the
 * step itself.
 *
 * The state describes the ACT and the dial, never the holding of a level:
 *   live     — the act runs in the API today and carries its weight
 *   not-yet  — the act, or the dial that would grant the level, does not exist
 *   proposed — specified, marked in the spec, not built
 * Nothing on this page claims a level the pool has not conferred.
 */
const STEPS: {
  level: string;
  name: string;
  state: StepState;
  stateLabel: string;
  granted: string;
  blurb: string;
  record: string[];
  carries: string;
  weight?: string;
  note?: string;
}[] = [
  {
    level: "level 01",
    name: "Contributor",
    state: "live",
    stateLabel: "live",
    granted: "granted by: a validated signed run",
    blurb:
      "You run benchmarks on your own hardware and submit signed results. One machine, one voice, but a real one on the record.",
    record: [
      "The submitter signs the payload digest with their Ed25519 key. Intake verifies that signature, verifies the digest and re-hashes every uploaded artifact before the run is stored.",
      "Only a validated run that declares a source class reaches the leaderboard. A signed run enters as measured_signed.",
    ],
    carries: "the run joins the pool as a measured_signed source, and the account is counted in the contributor export",
    weight: "×2 per validated signed run · live",
  },
  {
    level: "level 02",
    name: "Replicator",
    state: "not-yet",
    stateLabel: "not yet",
    granted: "granted by: validated reproductions",
    blurb:
      "You independently reproduce other contributors' runs, confirming or contradicting reported numbers.",
    record: [
      "The API holds no reproduction record and offers no endpoint that creates one. A second pair of hands on the same cell has nothing to write into yet.",
      "The weight a reproduction would carry is the last step of this ladder, marked proposed.",
    ],
    carries: "nothing yet — there is no reproduction for the pool to weigh",
    note: "threshold: proposal - dial pending owner",
  },
  {
    level: "level 03",
    name: "Auditor",
    state: "not-yet",
    stateLabel: "not yet",
    granted: "granted by: confirmed fake caught + reproductions",
    blurb:
      "You defend the pool: replicate high-impact cells and report unreal runs through moderation.",
    record: [
      "The reporting half is live. A signed-in reporter opens a report against a run or a claim under one of five categories. The API requires an identified reporter, and a report with no identity scores nothing.",
      "A handle listed as a moderator confirms or dismisses it. A confirmation against a claim marks that claim refuted, and it records the award for the reporter, which the contributor export counts.",
    ],
    carries: "the report, the moderator decision and the refuted claim. The reproduction half of the level waits with level 02",
    weight: "×5 per confirmed fake caught · live",
    note: "threshold: proposal - dial pending owner",
  },
  {
    level: "rung 04 · proposed",
    name: "Reproduction tier",
    state: "proposed",
    stateLabel: "proposed · not yet built",
    granted: "granted by: nothing yet",
    blurb:
      "A reproduction of another contributor's run, at ×3. The tier is written down and lands with the reproduce flow.",
    record: [
      "The contributor export carries two weights today: validated signed runs at ×2 and confirmed fake-caught reports at ×5. Reproduction is the third row of the published scoring table, not a column in the query.",
      "No flow produces a reproduction, so no account can hold this tier and no weight depends on it.",
    ],
    carries: "nothing yet — no flow produces a reproduction to weigh",
    note: "the ×3 reproduction reward is marked proposal; it lands with the reproduce flow",
  },
];

export default async function TrackRecordPage() {
  if ((await currentView()) === "agent") {
    return (
      <AgentView>
        {[
          "bestmodel.run / track record — agent view",
          "",
          "Trust is a ladder climbed by verified acts. Four steps, read top to bottom.",
          "The state of a step describes the act and the dial, not the holding of a level.",
          "",
          "  01 contributor   live     granted by: a validated signed run",
          "                         x2 per validated signed run (contributor export)",
          "  02 replicator    not yet  granted by: validated reproductions",
          "                         threshold: proposal - dial pending owner",
          "  03 auditor       not yet  granted by: confirmed fake caught + reproductions",
          "                         x5 per confirmed fake caught (contributor export)",
          "                         threshold: proposal - dial pending owner",
          "  04 reproduction  proposed granted by: nothing yet",
          "                         reproduction of another contributor's run, x3",
          "                         not yet built - lands with the reproduce flow",
          "",
          "Reporting a run or claim as unreal is live: a signed-in reporter opens the",
          "report under one of five categories, a handle in MODERATOR_HANDLES",
          "confirms or dismisses it, and a confirmation against a claim marks that",
          "claim refuted. The reporter is recorded.",
          "",
          "Account tier is a separate ledger from the ladder above: points arrive when",
          "a claim settles as verified (25 to the claimant, plus 15 when the vote",
          "margin had gone against that claim). Tier L0 to L4 at 100/340/750/1500 points.",
          "Tier sets vote weight 0.2 to 1.0 and posting limits, 2-50 claims per 24h",
          "and 5-250 votes per hour.",
          "",
          "A rung reads as held on a profile only when the API returns a badge naming",
          "it. The vocabulary is first_verified_run, giant_killer, pool_contributor_100h,",
          "claim_settler, rig_collector. One names a contributor, none names a",
          "replication or an audit, and the API has no request path that writes a",
          "badge row at all.",
        ].join("\n")}
      </AgentView>
    );
  }

  return (
    <main>
      <section className="page-head tr-head">
        <p className="kicker">bestmodel.run / track record</p>
        <h1>Trust is a ladder, climbed by verified acts</h1>
        <p className="tr-lede">
          Each level is granted by a verified act, never self-declared, and does not decay. A signed
          run is attributable to an Ed25519 key; a moderation act to the account that filed it.
          Three acts sit under this ladder: a signed run, a moderation decision, and a reproduction
          the API still has no endpoint for.
        </p>
        <div className="actions">
          <a className="btn primary" href="/console">
            start contributing -&gt;
          </a>
        </div>
      </section>

      <section className="section" aria-labelledby="tr-ladder-h">
        <h2 id="tr-ladder-h">The ladder</h2>
        <p className="section-copy">
          Four steps, top to bottom. Each names the act that grants it, what the pool records when
          that act happens, and the state of the step. <b>live</b> means the act runs in the API
          today. <b>not yet</b> means the act, or the dial that would grant the level, does not
          exist. <b>proposed</b> means written down, not built.
        </p>

        <ol className="tr-ladder">
          {STEPS.map((step) => (
            <li className="tr-step" key={step.name} data-state={step.state}>
              <span className="tr-node" aria-hidden="true" />
              <div className="tr-body">
                <div className="tr-eyebrow">
                  <span className="tr-level">{step.level}</span>
                  <span className="tr-status" data-state={step.state}>
                    {step.stateLabel}
                  </span>
                </div>
                <h3 className="tr-name">{step.name}</h3>
                <p className="tr-act">{step.granted}</p>
                <p className="tr-blurb">{step.blurb}</p>
                <div className="tr-record">
                  <span className="tr-record-k">what the pool records</span>
                  {step.record.map((line) => (
                    <p key={line}>{line}</p>
                  ))}
                  <span className="tr-record-k tr-record-k2">what it carries</span>
                  <p>{step.carries}</p>
                  {step.weight ? <p className="tr-weight">{step.weight}</p> : null}
                  {step.note ? <p className="tr-note">{step.note}</p> : null}
                </div>
              </div>
            </li>
          ))}
        </ol>
        <p className="tr-assume">
          Levels assume the one before them: a contributor who never reproduces another party&apos;s
          run stays a contributor. Points derive from signed activity only, and nothing is handed
          out.
        </p>
      </section>

      <section className="section tr-foot">
        <p>
          Nothing here is self-declared, and nothing here is a badge count. A rung reads as held on
          a profile only when the API returns a badge whose code names it. The badge vocabulary is
          short:{" "}
          <code className="tr-code">first_verified_run</code>,{" "}
          <code className="tr-code">giant_killer</code>,{" "}
          <code className="tr-code">pool_contributor_100h</code>,{" "}
          <code className="tr-code">claim_settler</code>,{" "}
          <code className="tr-code">rig_collector</code>. Only{" "}
          <code className="tr-code">pool_contributor_100h</code> names one of these three levels,
          the contributor. No badge code names a replication or an audit, so those two rungs cannot
          be held on a profile today, and the API has no request path that writes a badge row at
          all. The ladder above states what each act is worth, not who holds it.
        </p>
        <p>
          The account tier a profile shows is a separate ledger from the ladder. Points arrive when
          a claim settles as verified: 25 for the claimant, plus 15 more when the vote margin had
          gone against that claim. The tier runs L0 to L4 at 100, 340, 750 and 1500 points, and it
          is what sets vote weight, from 0.2 to 1.0, and posting limits, from 2 to 50 claims a day
          and 5 to 250 votes an hour.
        </p>
        <p>
          The weights on this page belong to the contributor export, which counts validated signed
          runs and confirmed fake-caught reports per handle. The community measures, the CLI signs,
          anyone can run the same cell — and every weight above is computed from that signed
          record, nothing else. A weight the export cannot produce stays out of reach, and the
          ladder names only what the pool has already weighed.
        </p>
        <p className="tr-note">
          read from the code: apps/public-api/src/services/create_run_report.py ·
          apps/public-api/src/dependencies/database_session_provider.py ·
          apps/intake-worker/src/reputation_policy.py
        </p>
      </section>
    </main>
  );
}
