// blog.ts — BM-BLOG-1 loader for content/blog/*.mdx.
// No MDX compiler is installed. gray-matter splits YAML frontmatter from the
// body; marked renders the body as HTML. JSX/MDX components in a post are
// not supported — files are markdown with a .mdx extension.

import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import matter from "gray-matter";
import { marked } from "marked";

// The production origin: bestmodel.run 308-redirects to www.bestmodel.run,
// so every absolute URL (canonical, og:image, JSON-LD) names the URL that is
// actually served. A canonical pointing at the redirect loses the signal.
export const BLOG_ORIGIN = "https://www.bestmodel.run";

export type BlogPost = {
  title: string;
  slug: string;
  date: string;
  description: string;
  author?: string;
  /** Site-relative path of the cover image, kept only when the file exists. */
  coverImage?: string;
  /** Measured numbers shown on the cover, kept for the cover renderer. */
  coverStats?: string;
  body: string;
  sourceFile: string;
};

export type FaqPair = { question: string; answer: string };

function resolveBlogDir(): string {
  const candidates = [
    path.join(process.cwd(), "content", "blog"),
    path.join(process.cwd(), "apps", "web-next", "content", "blog"),
  ];
  for (const dir of candidates) {
    if (existsSync(dir)) return dir;
  }
  throw new Error("content/blog not found next to the web app");
}

function resolvePublicDir(): string {
  const candidates = [
    path.join(process.cwd(), "public"),
    path.join(process.cwd(), "apps", "web-next", "public"),
  ];
  for (const dir of candidates) {
    if (existsSync(dir)) return dir;
  }
  return "";
}

/** True when the cover file is really there: a post must never render a broken image. */
export function coverExists(coverPath: string): boolean {
  const publicDir = resolvePublicDir();
  if (!publicDir) return false;
  const rel = coverPath.replace(/^\/+/, "");
  if (!rel || rel.includes("..")) return false;
  return existsSync(path.join(publicDir, rel));
}

function optionalString(data: Record<string, unknown>, key: string): string | undefined {
  const value = data[key];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function requireString(data: Record<string, unknown>, key: string, file: string): string {
  const value = data[key];
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`content/blog/${file}: frontmatter.${key} must be a non-empty string`);
  }
  return value.trim();
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Drop a leading ATX h1 when it repeats the frontmatter title (one h1 on the page). */
export function stripMatchingTitleHeading(markdown: string, title: string): string {
  return markdown.replace(new RegExp(`^\\s*#\\s+${escapeRegExp(title)}\\s*\\n+`), "");
}

export function renderMarkdown(markdown: string): string {
  const html = marked.parse(markdown, { async: false, gfm: true });
  if (typeof html !== "string") {
    throw new Error("marked.parse returned a promise; pass { async: false }");
  }
  return html;
}

export function canonicalFor(slug: string): string {
  return `${BLOG_ORIGIN}/blog/${slug}`;
}

/**
 * Q&A pairs of the "## Perguntas frequentes" section, for the FAQPage
 * JSON-LD. The answers come from the same text the reader sees, so the
 * structured data can never promise something the page does not say.
 */
export function faqPairs(markdown: string): FaqPair[] {
  const section = /^##[ \t]+Perguntas frequentes[ \t]*\r?\n([\s\S]*?)(?=^##[ \t]|(?![\s\S]))/m.exec(markdown);
  if (!section) return [];
  const pairs: FaqPair[] = [];
  for (const block of section[1].split(/^###[ \t]+/m).slice(1)) {
    const [question, ...rest] = block.split(/\r?\n/);
    const answer = rest.join(" ").replace(/\s+/g, " ").trim();
    if (question.trim() && answer) pairs.push({ question: question.trim(), answer });
  }
  return pairs;
}

export function listPosts(): BlogPost[] {
  const dir = resolveBlogDir();
  const files = readdirSync(dir).filter((name) => name.endsWith(".mdx"));
  const seen = new Set<string>();
  const posts: BlogPost[] = [];

  for (const file of files) {
    const raw = readFileSync(path.join(dir, file), "utf8");
    const parsed = matter(raw);
    const data = parsed.data as Record<string, unknown>;
    const title = requireString(data, "title", file);
    const slug = requireString(data, "slug", file);
    const date = requireString(data, "date", file);
    const description = requireString(data, "description", file);
    if (seen.has(slug)) {
      throw new Error(`content/blog: duplicate frontmatter.slug "${slug}"`);
    }
    seen.add(slug);
    const author = optionalString(data, "author");
    const cover = optionalString(data, "coverImage");
    posts.push({
      title,
      slug,
      date,
      description,
      author,
      coverImage: cover && coverExists(cover) ? cover : undefined,
      coverStats: optionalString(data, "coverStats"),
      body: parsed.content.replace(/^\uFEFF?/, ""),
      sourceFile: file,
    });
  }

  return posts.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : a.slug.localeCompare(b.slug)));
}

export function getPostBySlug(slug: string): BlogPost | undefined {
  return listPosts().find((post) => post.slug === slug);
}
