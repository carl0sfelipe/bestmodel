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

// "The wall" now names the capture feed at /claims — the social surface.
// The measured pool keeps its route at /wall and is labelled "Pool", which is
// what it has always actually been. Route, content and metadata are unchanged.
export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const view = await currentView();
  return (
    <html lang="en" data-view={view}>
      <body>
        <header className="site-nav">
          <Link className="brand" href="/">$bestmodel.run</Link>
          <nav>
            <Link href="/claims">The wall</Link>
            <Link href="/submit">Capture</Link>
            <Link href="/wall">Pool</Link>
            <Link href="/hardware">Hardware</Link>
            <Link href="/cloud-anchors">Cloud anchors</Link>
            <Link href="/track-record">Track record</Link>
            <Link href="/mural">Mural</Link>
            <Link href="/console">Console</Link>
          </nav>
          <ViewToggle view={view} />
        </header>
        {children}
        <footer>
          <span>bestmodel.run</span>
          <span>community pool data · every number declares its basis</span>
        </footer>
      </body>
    </html>
  );
}
