import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "bestmodel.run", template: "%s — bestmodel.run" },
  description: "An honest compatibility engine for local AI, built from community pool measurements.",
  robots: { index: true, follow: true },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#0B0C0E" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><header className="site-nav"><Link className="brand" href="/">$bestmodel.run</Link><nav><Link href="/hardware">Hardware</Link><Link href="/wall">The wall</Link><Link href="/track-record">Track record</Link><Link href="/mural">Mural</Link><Link href="/console">Console</Link></nav></header>{children}<footer><span>bestmodel.run</span><span>community pool data · every number declares its basis</span></footer></body></html>;
}
