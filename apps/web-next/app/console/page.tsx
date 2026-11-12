import type { Metadata } from "next";

import ConsoleClient from "./console-client";

// The console is the no-terminal surface of the capture network: sign in with
// a passkey, follow rigs and people, read the mixed feed and your
// notifications. Reads stay public; only writes need the account.
export const metadata: Metadata = {
  title: "Console",
  description:
    "Sign in with a passkey and follow rigs, read the community feed, and capture your own runs.",
  robots: { index: true, follow: true },
};

export default function ConsolePage() {
  return <ConsoleClient />;
}
