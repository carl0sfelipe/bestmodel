import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  canonicalFor,
  getPostBySlug,
  listPosts,
  renderMarkdown,
  stripMatchingTitleHeading,
} from "../../../lib/blog";
import { currentView } from "../../../lib/view-server";
import AgentView from "../../_components/agent-view";

export function generateStaticParams() {
  return listPosts().map((post) => ({ slug: post.slug }));
}

export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) return { title: "Blog" };
  return {
    title: post.title,
    description: post.description,
    alternates: { canonical: canonicalFor(post.slug) },
  };
}

function articleJsonLd(post: NonNullable<ReturnType<typeof getPostBySlug>>) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.description,
    datePublished: post.date,
    url: canonicalFor(post.slug),
    mainEntityOfPage: canonicalFor(post.slug),
    author: post.author ? { "@type": "Person", name: post.author } : { "@type": "Organization", name: "bestmodel.run" },
    publisher: { "@type": "Organization", name: "bestmodel.run", url: "https://bestmodel.run" },
  };
}

export default async function BlogPostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) notFound();

  if ((await currentView()) === "agent") {
    return (
      <AgentView>
        {[
          `bestmodel.run / blog — ${post.title}`,
          "",
          `date ${post.date}${post.author ? ` · ${post.author}` : ""}`,
          post.description,
          "",
          post.body.trim(),
        ].join("\n")}
      </AgentView>
    );
  }

  const html = renderMarkdown(stripMatchingTitleHeading(post.body, post.title));
  return (
    <main>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd(post)) }} />
      <article className="blog-post">
        <header className="blog-post-head">
          <p className="kicker">bestmodel.run / blog</p>
          <h1>{post.title}</h1>
          <p className="blog-post-meta">
            <time dateTime={post.date}>{post.date}</time>
            {post.author ? ` · ${post.author}` : ""}
          </p>
        </header>
        <div className="blog-prose" dangerouslySetInnerHTML={{ __html: html }} />
      </article>
    </main>
  );
}
