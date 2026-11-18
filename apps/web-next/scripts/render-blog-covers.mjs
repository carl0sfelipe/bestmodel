#!/usr/bin/env node
// render-blog-covers.mjs — draws the cover of every blog post.
//
// The cover is a static PNG in public/images/blog/, rendered from
// scripts/blog-cover-template.html with headless Chromium. No GPU, no network
// beyond the web fonts (the renderer waits for them before the screenshot).
//
//   node scripts/render-blog-covers.mjs            # every post
//   node scripts/render-blog-covers.mjs <slug> ... # only these
//
// The numbers on the cover come from the post front matter (coverStats): the
// same measured facts the text uses.
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
import matter from "gray-matter";

const APP = path.resolve(import.meta.dirname, "..");
const CONTENT = path.join(APP, "content", "blog");
const OUT = path.join(APP, "public", "images", "blog");
const TEMPLATE = path.join(APP, "scripts", "blog-cover-template.html");
const WIDTH = 1424;
const HEIGHT = 752;

const CHROMIUM_CANDIDATES = [
  process.env.CHROMIUM_BIN,
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
].filter(Boolean);

function chromiumBin() {
  for (const bin of CHROMIUM_CANDIDATES) {
    if (existsSync(bin)) return bin;
  }
  throw new Error("no Chromium found; set CHROMIUM_BIN");
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** *word* becomes <em>word</em>; everything else is escaped. */
function titleHtml(title) {
  return title
    .split(/(\*[^*]+\*)/)
    .map((part) =>
      part.startsWith("*") && part.endsWith("*") && part.length > 2
        ? `<em>${escapeHtml(part.slice(1, -1))}</em>`
        : escapeHtml(part),
    )
    .join("");
}

/** Two letters of the first real word of the title: "Granite" -> "GR". */
function monogram(title) {
  const words = title.replace(/\*/g, "").split(/\s+/).filter(Boolean);
  const first = words.find((word) => word.replace(/[^\p{L}\p{N}]/gu, "").length >= 3) ?? words[0] ?? "";
  return first.replace(/[^\p{L}\p{N}]/gu, "").slice(0, 2).toUpperCase();
}

function chipsFor(post) {
  const stats = (post.coverStats || "")
    .split("·")
    .map((part) => part.trim())
    .filter(Boolean);
  if (stats.length === 0) return "";
  return stats.map((value) => `<span class="chip">${escapeHtml(value)}</span>`).join("");
}

/** Longer titles get a smaller size: the cover must not cut the title. */
function titleSize(title) {
  const length = title.replace(/\*/g, "").length;
  if (length <= 45) return "74px";
  if (length <= 70) return "62px";
  if (length <= 100) return "52px";
  return "44px";
}

function render(post, bin) {
  const template = readFileSync(TEMPLATE, "utf8");
  const html = template
    .replace("{{KICKER}}", "bestmodel.run / blog")
    .replace("{{TITLE}}", titleHtml(post.title))
    .replace("{{TITLE_SIZE}}", titleSize(post.title))
    .replace("{{STATS}}", chipsFor(post))
    .replace("{{TAG}}", escapeHtml(post.coverTag || post.date))
    .replace("{{MONOGRAM}}", escapeHtml(monogram(post.title)));
  const tmp = path.join(os.tmpdir(), `capa-${post.slug}.html`);
  writeFileSync(tmp, html, "utf8");
  const out = path.join(OUT, `capa-${post.slug}.png`);
  execFileSync(
    bin,
    [
      "--headless",
      "--no-sandbox",
      "--disable-gpu",
      "--hide-scrollbars",
      "--force-device-scale-factor=1",
      `--window-size=${WIDTH},${HEIGHT}`,
      "--virtual-time-budget=8000",
      `--screenshot=${out}`,
      `file://${tmp}`,
    ],
    { stdio: "ignore" },
  );
  if (!existsSync(out)) throw new Error(`cover not written: ${out}`);
  return out;
}

const only = process.argv.slice(2);
const bin = chromiumBin();
mkdirSync(OUT, { recursive: true });
let count = 0;
for (const file of readdirSync(CONTENT).filter((name) => name.endsWith(".mdx")).sort()) {
  const { data } = matter(readFileSync(path.join(CONTENT, file), "utf8"));
  const slug = typeof data.slug === "string" ? data.slug : file.replace(/\.mdx$/, "");
  if (only.length > 0 && !only.includes(slug)) continue;
  const title = typeof data.title === "string" ? data.title : slug;
  const out = render(
    {
      slug,
      title,
      date: String(data.date ?? ""),
      coverStats: data.coverStats,
      coverTag: data.coverTag,
    },
    bin,
  );
  console.log(`${slug} -> ${path.relative(APP, out)}`);
  count += 1;
}
console.log(`${count} cover(s) rendered in ${path.relative(APP, OUT)}`);
