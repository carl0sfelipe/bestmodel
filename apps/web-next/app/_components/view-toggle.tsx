// view-toggle.tsx — the human/agent switch rendered in the header (S32).
// aria-pressed is resolved on the server (the active view is known from the
// first byte); the links keep the current path and only swap ?as=, so the
// toggle is shareable like any ?as= link.

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { View } from "../../lib/view";

export default function ViewToggle({ view }: { view: View }) {
  const pathname = usePathname();
  const href = (as: View) => `${pathname}?as=${as}`;
  return (
    <span className="view-toggle" data-view-toggle>
      <Link href={href("human")} aria-pressed={view === "human"}>human</Link>
      <Link href={href("agent")} aria-pressed={view === "agent"}>agent</Link>
    </span>
  );
}
