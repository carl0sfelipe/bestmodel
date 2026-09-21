import { readFile } from "node:fs/promises";
import path from "node:path";
import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";

export const metadata = {
  title: "Get started",
  description: "From a clean checkout to measured numbers: build the CLI, read your hardware, rank models, run the lab.",
};

// Single source of truth (S33 contract): the rendered steps ARE
// docs/agent-quickstart.md — read at render time, never re-typed into JSX.
// outputFileTracingIncludes (next.config.ts) ships the file with the server
// bundle, so the relative path resolves both locally and on Vercel.
async function loadGuide(): Promise<string> {
  const candidates = [
    // Vercel: outputFileTracingIncludes copies ../docs/agent-quickstart.md
    // (relative to the app dir) into the server bundle.
    path.join(process.cwd(), "..", "docs", "agent-quickstart.md"),
    // Local `npm start` from apps/web-next: repo root is two levels up.
    path.join(process.cwd(), "..", "..", "docs", "agent-quickstart.md"),
    path.join(process.cwd(), "docs", "agent-quickstart.md"),
  ];
  for (const candidate of candidates) {
    try {
      return await readFile(candidate, "utf8");
    } catch {
      /* try the next location */
    }
  }
  throw new Error("docs/agent-quickstart.md not found next to the web app");
}

export default async function CliPage() {
  const guide = await loadGuide();
  if ((await currentView()) === "agent") {
    return (
      <AgentView>
        {[
          "bestmodel.run / cli — getting started (agent twin)",
          "",
          "Single source of truth: docs/agent-quickstart.md (executed clean on 2026-09-18).",
          "Runnable today: cargo build from source · benchmark-probe · benchmark-probe lab · make agent-smoke.",
          "plan / report / contribute: not shipped yet — never invoke them.",
          "",
          guide,
        ].join("\n")}
      </AgentView>
    );
  }
  return (
    <main>
      <section className="page-head">
        <p className="kicker">bestmodel.run / get started</p>
        <h1>From clone to<br />measured numbers.</h1>
        <p>
          The whole CLI story in one honest guide: build from source, read the
          hardware you are on, rank the best models for it against the pool,
          then measure it yourself. No API key, no token, no installer —
          there is no one-line installer yet.
        </p>
        <div className="actions">
          <a className="btn primary" href="https://github.com/carl0sfelipe/bestmodel">clone the repo -&gt;</a>
          <a className="btn" href="/wall?as=human">see what the pool already measures</a>
        </div>
      </section>
      <section className="section">
        <div className="cli-note">
          <strong>Not shipped yet:</strong> <code>report</code> and{" "}
          <code>contribute</code> (the CLI v2 lab loop) are specified in{" "}
          <a href="https://github.com/carl0sfelipe/bestmodel/blob/main/specs/en/L01-cli-v2-local-lab.md">L01</a>{" "}
          but not in the binary you can build today. The commands below only
          document what runs — never invoke a subcommand this page does not show.
        </div>
        <article className="cli-doc">
          <pre>{guide}</pre>
        </article>
      </section>
    </main>
  );
}
