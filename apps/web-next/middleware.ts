// middleware.ts — resolves the ?as= view on every request (S32).
// The resolved view travels to server components as the x-bm-view request
// header, so the correct view is in the first byte of HTML: no flash, and
// curl / crawlers get the right twin without running client JS.
// The choice persists to the bm_view cookie ONLY when it came from an
// explicit ?as= / ?view= — auto-detection is never written (journey.js rule).

import { NextResponse, type NextRequest } from "next/server";
import { resolveView, VIEW_COOKIE } from "./lib/view";

export function middleware(request: NextRequest) {
  const { view, reason } = resolveView(
    request.nextUrl.searchParams,
    request.headers.get("user-agent"),
    request.cookies.get(VIEW_COOKIE)?.value ?? null,
  );

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-bm-view", view);
  const response = NextResponse.next({ request: { headers: requestHeaders } });

  if (reason === "url") {
    response.cookies.set(VIEW_COOKIE, view, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
    });
  }
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|data).*)"],
};
