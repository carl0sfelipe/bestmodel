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
          "Runnable today: cargo build from source · benchmark-probe (detect, estimate) ·",
          "lab · plan · report · contribute · login · make agent-smoke.",
          "The whole documented loop dispatches in the binary (D10) — never invoke a",
          "subcommand this page does not document.",
          "",
          guide,
        ].join("\n")}
      </AgentView>
    );
  }
  return (
    <main>
      <article className="runbook">
        <header className="runbook-head">
          <h1>From clone to measured numbers</h1>
          <p className="runbook-src">
            source of truth: <code>docs/agent-quickstart.md</code> in the repo — executed clean on
            2026-09-18, rendered here verbatim. No installer and no API key: build from source.
          </p>
        </header>
        <pre className="runbook-body">{guide}</pre>
        <footer className="runbook-foot">
          <a className="btn primary" href="https://github.com/carl0sfelipe/bestmodel">clone the repo</a>
          <a className="btn" href="/wall?as=human">see what the pool already measures</a>
        </footer>
      </article>
    </main>
  );
}
