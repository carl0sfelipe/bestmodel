import ProfileClient from "./profile-client";

export async function generateMetadata({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  return {
    title: `@${handle}`,
    description: `Track record for @${handle}: verified acts, reputation, and public rigs.`,
  };
}

export default async function ProfilePage({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  return <ProfileClient handle={handle} />;
}
