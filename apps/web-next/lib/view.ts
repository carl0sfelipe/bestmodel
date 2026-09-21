// view.ts — the ?as= dual-view contract (S32), ported from the divergent
// Pages copy (apps/web/site/assets/journey.js). Pure and unit-testable: no
// next/* imports here, so middleware (edge) and server components can share it.
//
// Precedence (first hit wins), mirroring journey.js:
//   1. ?as= / ?view=        URL — shareable, deterministic
//   2. saved cookie bm_view explicit previous choice
//   3. known agent / LLM user-agent
//   4. search-crawler user-agent  Googlebot etc. → human
//   5. else human (browser default; journey.js asked, a server contract can't)
//
// Auto-detection is never persisted — only an explicit ?as= sticks.

export type View = "human" | "agent";
export type ViewReason = "url" | "saved" | "ua" | "search" | "default";

// Token list copied verbatim from journey.js — do not invent new agent names.
const AGENT_UA = new RegExp(
  [
    "GPTBot", "ChatGPT-User", "OAI-SearchBot",
    "ClaudeBot", "Claude-User", "anthropic-ai",
    "PerplexityBot", "Perplexity-User",
    "Google-Extended", "Applebot-Extended",
    "Amazonbot", "Bytespider", "CCBot",
    "meta-externalagent", "cohere-ai",
    "YouBot", "DuckAssistBot", "Diffbot",
    "AI2Bot", "iaskspider", "ImagesiftBot",
    "Timpibot", "Webzio-Extended", "PetalBot",
    "HuggingFace(?:Bot)?", "MetaAI", "PhindBot",
    "xAI-Grok", "GrokBot",
    "OpenHands", "SWE-agent", "Aiderbot",
  ].join("|"),
  "i",
);

// Copied verbatim from journey.js — search crawlers are readers, not agents.
const SEARCH_UA =
  /Googlebot|Bingbot|bingbot|Slurp|DuckDuckBot|Baiduspider|Yandex(?:Bot|Images)|facebookexternalhit|LinkedInBot|Twitterbot|Applebot(?!-Extended)|Chrome-Lighthouse|Lighthouse/i;

function norm(value: string | null | undefined): View | null {
  if (value === "agent" || value === "human") return value;
  return null;
}

export function resolveView(
  params: URLSearchParams | undefined,
  ua: string | null,
  cookie: string | null,
): { view: View; reason: ViewReason } {
  const explicit = norm(params?.get("as") ?? params?.get("view"));
  if (explicit) return { view: explicit, reason: "url" };
  const saved = norm(cookie);
  if (saved) return { view: saved, reason: "saved" };
  if (ua && AGENT_UA.test(ua)) return { view: "agent", reason: "ua" };
  if (ua && SEARCH_UA.test(ua)) return { view: "human", reason: "search" };
  return { view: "human", reason: "default" };
}

export const VIEW_COOKIE = "bm_view";
