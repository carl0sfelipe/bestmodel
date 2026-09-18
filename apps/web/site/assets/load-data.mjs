// S4 — shared derived-data loader. Data only: no DOM, no engine import.
// Paths anchor at the SITE ROOT derived from this module's own URL, so
// they work from site/ and site/m/ pages AND under a subpath host
// (GitHub Pages preview at <user>.github.io/<repo>/) — "../../" walking
// would escape to the host root and break there.

const SITE_ROOT = new URL(import.meta.url.replace(/(?:m\/)?assets\/load-data\.mjs$/, ""));

let cache = null;

export async function loadDerived() {
  if (cache) return cache;
  const files = [
    ["hardware", "hardware.json"],
    ["models", "models.json"],
    ["pool", "pool.json"],
    ["stats", "stats.json"],
  ];
  const loaded = {};
  try {
    await Promise.all(files.map(async ([name, file]) => {
      const url = new URL(`data/derived/${file}`, SITE_ROOT);
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${url.pathname}: HTTP ${res.status}`);
      loaded[name] = await res.json();
    }));
  } catch (err) {
    cache = null;
    throw new Error(`loadDerived: ${err.message}`);
  }
  cache = loaded;
  return cache;
}
