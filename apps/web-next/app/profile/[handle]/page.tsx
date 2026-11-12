import { currentView } from "../../../lib/view-server";
import AgentView from "../../_components/agent-view";
import ProfileClient from "./profile-client";
import "./profile.css";

export async function generateMetadata({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  return {
    title: `@${handle}`,
    description: `The record of @${handle}: reputation, trust level, captured claims and public rigs.`,
  };
}

export default async function ProfilePage({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  if ((await currentView()) === "agent") {
    return (
      <AgentView>
        {[
          `bestmodel.run / profile — @${handle} (agent view)`,
          "",
          "A contributor profile: verified acts, reputation points and tier,",
          "public rigs, and follow state. This page is a live client; the record",
          "itself is the machine surface:",
          "",
          `  GET /v1/users/${handle}   handle, reputation{points,tier}, rigs[], follow counts`,
          `  POST /v1/users/${handle}/follow   (auth; DELETE unfollows)`,
          "  GET /v1/claims?sort=recent   the wall; rows whose claimant_handle",
          `  matches "${handle}" are this account's captures`,
          "",
          "Trust ladder: /track-record?as=agent · full contract: /llms.txt",
        ].join("\n")}
      </AgentView>
    );
  }
  return <ProfileClient handle={handle} />;
}
