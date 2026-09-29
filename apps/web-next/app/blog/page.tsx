import Link from "next/link";
import { listPosts } from "../../lib/blog";
import { currentView } from "../../lib/view-server";
import AgentView from "../_components/agent-view";

export const metadata = {
  title: "Blog",
  description: "Measured local-AI notes: which model fits a GPU, how fast, and how to add a signed run.",
  alternates: { canonical: "https://bestmodel.run/blog" },
};

export default async function BlogIndexPage() {
  const posts = listPosts();
  if ((await currentView()) === "agent") {
    const lines = posts.flatMap((post) => [
      `  ${post.date}  /blog/${post.slug}`,
      `  ${post.title}`,
      `  ${post.description}`,
      "",
    ]);
    return (
      <AgentView>
        {[
          "bestmodel.run / blog — agent view",
          "",
          "Posts newest first. Each post: /blog/<slug>?as=agent.",
          "",
          ...lines,
        ].join("\n")}
      </AgentView>
    );
  }
  return (
    <main>
      <section className="blog-index">
        <header className="blog-index-head">
          <p className="kicker">bestmodel.run / blog</p>
          <h1>Blog</h1>
          <p>Measured local-AI notes: which model fits a GPU, how fast, and how to add a signed run.</p>
        </header>
        <ol className="blog-index-list">
          {posts.map((post) => (
            <li key={post.slug}>
              <Link href={`/blog/${post.slug}`}>
                <time dateTime={post.date}>{post.date}</time>
                <h2>{post.title}</h2>
                <p>{post.description}</p>
              </Link>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
