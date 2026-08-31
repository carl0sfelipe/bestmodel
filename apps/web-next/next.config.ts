import type { NextConfig } from "next";

/**
 * The app calls the API through lib/social.ts, whose base is
 * NEXT_PUBLIC_API_BASE ?? "". On Vercel that variable holds the absolute
 * https://api.bestmodel.run, so requests leave the origin directly and the
 * rewrite below never fires.
 *
 * Locally the base is "" and /v1/* would otherwise hit Next itself — which is
 * exactly the "the wall could not be loaded — HTTP 404" the owner saw. The
 * rewrite only registers when an origin is actually known, so a production
 * build can never silently proxy to a localhost that isn't there.
 *
 * Set API_ORIGIN in any deploy that wants same-origin /v1 (compose: http://api:8000).
 */
const API_ORIGIN =
  process.env.API_ORIGIN ??
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8010" : null);

const nextConfig: NextConfig = {
  async rewrites() {
    if (!API_ORIGIN) return [];
    return [{ source: "/v1/:path*", destination: `${API_ORIGIN}/v1/:path*` }];
  },
};

export default nextConfig;
