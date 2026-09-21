// view-server.ts — server-side read of the view the middleware resolved.
// Server components (layout and pages) call currentView() instead of parsing
// the request themselves, so the mechanism lives in exactly one place.

import { headers } from "next/headers";
import type { View } from "./view";

export async function currentView(): Promise<View> {
  const value = (await headers()).get("x-bm-view");
  return value === "agent" ? "agent" : "human";
}
