import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { currentView } from "../lib/view-server";
import ViewToggle from "./_components/view-toggle";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "bestmodel.run", template: "%s — bestmodel.run" },
  description: "An honest compatibility engine for local AI, built from community pool measurements.",
  robots: { index: true, follow: true },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#0B0C0E" };

// Chrome per design.md (S43): a mono masthead (brand + one-line tagline, then
// an index row) instead of the N1a single-row fingerprint, and a statement
// footer — the honesty ladder as a sentence — instead of a link farm.
// "The wall" names the capture feed at /claims; the measured pool is "Pool".
export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const view = await currentView();
  return (
    <html lang="en" data-view={view}>
      <body>
        <header className="site-nav masthead">
          <div className="mast-top">
            <Link className="brand" href="/">$ bestmodel.run</Link>
            <p className="mast-tag">an honest compatibility engine for local AI</p>
            <ViewToggle view={view} />
          </div>
          <nav className="mast-index" aria-label="Site index">
            <Link href="/cli">get started</Link>
            <Link href="/claims">the wall</Link>
            <Link href="/submit">capture</Link>
            <Link href="/wall">pool</Link>
            <Link href="/hardware">hardware</Link>
            <Link href="/cloud-anchors">cloud anchors</Link>
            <Link href="/track-record">track record</Link>
            <Link href="/mural">mural</Link>
            <Link href="/console">console</Link>
          </nav>
        </header>
        {children}
        <footer className="statement">
          <p className="statement-line">
            $ bestmodel.run — measured &gt; reported &gt; extrapolated &gt; formula &gt; no data yet.
          </p>
          <p className="statement-note">
            Every number on this site declares its basis. The pool is a frozen snapshot, not live
            throughput.
          </p>
        </footer>
      </body>
    </html>
  );
}
