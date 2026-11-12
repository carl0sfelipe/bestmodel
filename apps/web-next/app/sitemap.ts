import type { MetadataRoute } from "next";
import { listPosts } from "../lib/blog";
import { loadDerived } from "../lib/engine";

// The pool snapshot date is the only date these pages can honestly claim:
// the numbers they render are frozen at that moment. The static pages change
// with every deploy, so they carry the deploy date.
const POOL_SNAPSHOT = new Date(loadDerived().stats.snapshotAt ?? "2026-09-18T00:00:00.000Z");
const DEPLOY_DATE = new Date("2026-11-12T00:00:00.000Z");

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://www.bestmodel.run";

  const poolPages = [
    "/",
    "/wall",
    "/claims",
    "/hardware",
    "/planejar",
    "/mural",
    "/submit",
    "/console",
    "/cloud-anchors",
    "/track-record",
    "/transparencia",
    "/cli",
    "/blog",
  ].map((path) => ({ url: `${base}${path}`, lastModified: DEPLOY_DATE }));

  const modelPages = loadDerived().models.map((model) => ({
    url: `${base}/m/${model.slug}`,
    lastModified: POOL_SNAPSHOT,
  }));

  const posts = listPosts().map((post) => ({
    url: `${base}/blog/${post.slug}`,
    lastModified: new Date(`${post.date}T00:00:00.000Z`),
  }));

  return [...poolPages, ...modelPages, ...posts];
}
