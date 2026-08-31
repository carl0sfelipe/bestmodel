import type { NextConfig } from "next";

/**
 * The app calls the API same-origin at /v1/* (lib/social.ts uses base "").
 * Nothing was routing that prefix, so every social call hit Next itself and
 * came back 404 — "the wall could not be loaded — HTTP 404".
 *
 * This is the rewrite the brief assumed the deploy already had.
 * deploy/Caddyfile only publishes api.bestmodel.run, so set API_ORIGIN there
 * (e.g. http://api:8000 inside compose) rather than relying on the local default.
 */
const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8010";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/v1/:path*", destination: `${API_ORIGIN}/v1/:path*` }];
  },
};

export default nextConfig;
