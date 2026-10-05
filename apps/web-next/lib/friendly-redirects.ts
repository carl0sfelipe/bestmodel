// friendly-redirects.ts — soft redirects for the short URLs people and
// agents guess (bestmodel.run /cloud, /agent, /api, ...).
// Pure: no next/* imports, so next.config.ts and node --test share it.

export type FriendlyRedirect = {
  source: string;
  destination: string;
  permanent: boolean;
};

export const FRIENDLY_REDIRECTS: readonly FriendlyRedirect[] = [
  { source: "/cloud", destination: "/cloud-anchors", permanent: false },
  { source: "/anchors", destination: "/cloud-anchors", permanent: false },
  { source: "/cloud-anchor", destination: "/cloud-anchors", permanent: false },
  { source: "/agent", destination: "/llms.txt", permanent: false },
  { source: "/agents", destination: "/llms.txt", permanent: false },
  { source: "/api", destination: "/llms.txt", permanent: false },
];

const TARGETS = new Map<string, string>(
  FRIENDLY_REDIRECTS.map((entry) => [entry.source.toLowerCase(), entry.destination]),
);

export function resolveFriendlyRedirect(pathname: string): string | null {
  const trimmed =
    pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
  return TARGETS.get(trimmed.toLowerCase()) ?? null;
}
