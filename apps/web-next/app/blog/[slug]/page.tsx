import type { Metadata } from "next";
import Image from "next/image";
import { notFound } from "next/navigation";
import {
  BLOG_ORIGIN,
  canonicalFor,
  faqPairs,
  getPostBySlug,
  listPosts,
  renderMarkdown,
  stripMatchingTitleHeading,
  type FaqPair,
} from "../../../lib/blog";
import { currentView } from "../../../lib/view-server";
import AgentView from "../../_components/agent-view";
import CtaUtm from "../../_components/cta-utm";

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
  const image = post.coverImage ? `${BLOG_ORIGIN}${post.coverImage}` : undefined;
  return {
    title: post.title,
    description: post.description,
    alternates: { canonical: canonicalFor(post.slug) },
    ...(image
      ? {
          openGraph: {
            title: post.title,
            description: post.description,
            url: canonicalFor(post.slug),
            type: "article" as const,
            publishedTime: post.date,
            images: [{ url: image, width: 1424, height: 752, alt: post.title }],
          },
          twitter: {
            card: "summary_large_image" as const,
            title: post.title,
            description: post.description,
            images: [image],
          },
        }
      : {}),
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
    ...(post.coverImage ? { image: `${BLOG_ORIGIN}${post.coverImage}` } : {}),
    author: post.author ? { "@type": "Person", name: post.author } : { "@type": "Organization", name: "bestmodel.run" },
    publisher: { "@type": "Organization", name: "bestmodel.run", url: BLOG_ORIGIN },
  };
}

function faqJsonLd(pairs: FaqPair[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: pairs.map((pair) => ({
      "@type": "Question",
      name: pair.question,
      acceptedAnswer: { "@type": "Answer", text: pair.answer },
    })),
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
  const faq = faqPairs(post.body);
  return (
    <main>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd(post)) }} />
      {faq.length > 0 ? (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd(faq)) }} />
      ) : null}
      <article className="blog-post">
        <header className="blog-post-head">
          <p className="kicker">bestmodel.run / blog</p>
          <h1>{post.title}</h1>
          <p className="blog-post-meta">
            <time dateTime={post.date}>{post.date}</time>
            {post.author ? ` · ${post.author}` : ""}
          </p>
        </header>
        {post.coverImage ? (
          <figure className="blog-cover">
            <Image
              src={post.coverImage}
              alt={post.title}
              width={1424}
              height={752}
              sizes="(max-width: 1100px) 100vw, 720px"
              priority
            />
          </figure>
        ) : null}
        <div className="blog-prose" dangerouslySetInnerHTML={{ __html: html }} />
        <CtaUtm />
      </article>
    </main>
  );
}
