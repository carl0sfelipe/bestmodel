import { NextResponse } from "next/server";
import { featureEmBreve } from "../../../../lib/em-breve";

export async function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const feature = featureEmBreve(slug);
  if (!feature) {
    return NextResponse.json({ status: "not_found" }, { status: 404 });
  }
  return NextResponse.json(
    {
      status: "not_implemented",
      feature: feature.slug,
      oQueFaz: feature.oQueFaz,
      comoAjudar: feature.comoAjudar,
    },
    { status: 501 },
  );
}
