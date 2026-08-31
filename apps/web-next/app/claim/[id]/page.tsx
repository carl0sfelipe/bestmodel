import ClaimClient from "./claim-client";

export const metadata = {
  title: "Claim",
  description:
    "A captured benchmark claim: the number, where it was found, what the measured pool says, and how the community voted.",
};

export default async function ClaimPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ClaimClient id={id} />;
}
