// agent-view.tsx — the shared agent/TUI twin wrapper (S32 contract).
// Deterministic monospace text, no animation, no client JS: everything an
// agent sees is in the HTML that curl gets. The children are plain text
// built from the same server data the human view renders.

import type { ReactNode } from "react";

export default function AgentView({ children }: { children: ReactNode }) {
  return (
    <main data-view="agent" className="agent-view">
      <pre>{children}</pre>
    </main>
  );
}
