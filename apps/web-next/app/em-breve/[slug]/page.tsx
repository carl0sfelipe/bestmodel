import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FEATURES_EM_BREVE, featureEmBreve, issueUrlEmBreve } from "../../../lib/em-breve";
import { currentView } from "../../../lib/view-server";
import AgentView from "../../_components/agent-view";

export function generateStaticParams() {
  return FEATURES_EM_BREVE.map((feature) => ({ slug: feature.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const feature = featureEmBreve(slug);
  if (!feature) notFound();
  return {
    title: feature.titulo,
    description: feature.oQueFaz,
    robots: { index: false },
  };
}

export default async function EmBrevePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const feature = featureEmBreve(slug);
  if (!feature) notFound();

  const issueUrl = issueUrlEmBreve(feature.slug);
  const help = [
    { label: feature.comoAjudar[0], href: issueUrl, external: true, cta: "abrir issue ->" },
    { label: feature.comoAjudar[1], href: "/submit", external: false, cta: "enviar medição ->" },
    { label: feature.comoAjudar[2], href: "https://llms.surf", external: true, cta: "abrir llms.surf ->" },
  ];

  if ((await currentView()) === "agent") {
    return (
      <AgentView>
        {[
          `bestmodel.run / em breve — ${feature.titulo} (agent view)`,
          "",
          "Ainda não existe.",
          "",
          feature.oQueFaz,
          "",
          "Como ajudar a construir:",
          `  1. ${feature.comoAjudar[0]}`,
          `     ${issueUrl}`,
          `  2. ${feature.comoAjudar[1]}`,
          "     /submit",
          `  3. ${feature.comoAjudar[2]}`,
          "     https://llms.surf",
        ].join("\n")}
      </AgentView>
    );
  }

  return (
    <main>
      <section className="page-head">
        <p className="kicker">bestmodel.run / em breve</p>
        <h1>{feature.titulo}</h1>
        <p>Ainda não existe.</p>
        <p>{feature.oQueFaz}</p>
      </section>
      <section className="section">
        <h2>Como ajudar a construir</h2>
        <div className="card-grid">
          {help.map((item, index) => (
            <article className="card" key={item.href}>
              <small className="kicker">{`0${index + 1}`}</small>
              <p>{item.label}</p>
              <div className="actions">
                {item.external ? (
                  <a className="btn primary" href={item.href} rel="noreferrer">
                    {item.cta}
                  </a>
                ) : (
                  <Link className="btn primary" href={item.href}>
                    {item.cta}
                  </Link>
                )}
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
