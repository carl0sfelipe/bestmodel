// S4 — shared derived-data loader. Data only: no DOM, no engine import.
// Paths resolve relative to this module (../../data/derived/) so it works
// from both site/ and site/m/ pages.

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
      const url = new URL(`../../data/derived/${file}`, import.meta.url);
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
