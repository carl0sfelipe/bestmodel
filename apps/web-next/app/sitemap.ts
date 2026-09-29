import type { MetadataRoute } from "next";
import { listPosts } from "../lib/blog";
import { loadDerived } from "../lib/engine";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://bestmodel.run";
  const lastModified = new Date("2026-08-30T04:43:50.758Z");
  const pages = [
    "",
    "/hardware",
    "/wall",
    "/claims",
    "/submit",
    "/track-record",
    "/mural",
    "/console",
    "/blog",
    ...loadDerived().models.map((model) => `/m/${model.slug}`),
  ].map((path) => ({ url: `${base}${path}`, lastModified }));
  const posts = listPosts().map((post) => ({
    url: `${base}/blog/${post.slug}`,
    lastModified: new Date(`${post.date}T00:00:00.000Z`),
  }));
  return [...pages, ...posts];
}
