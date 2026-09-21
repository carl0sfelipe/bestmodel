// Intent catalog loader. The id list lives in packages/intent-catalog/catalog.json.
// BESTMODEL_INTENT_CATALOG overrides the path. Every export reads the file
// again so a test can point the env var at a fixture catalog.
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const defaultCatalog = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../packages/intent-catalog/catalog.json",
);

export function catalogPath() {
  return process.env.BESTMODEL_INTENT_CATALOG || defaultCatalog;
}

export function loadCatalog() {
  return JSON.parse(readFileSync(catalogPath(), "utf8"));
}

export function INTENTS() {
  return loadCatalog().intents;
}

export function STORABLE_CATEGORIES() {
  return INTENTS().filter((row) => row.storable).map((row) => row.id);
}

export function classifyModel(display, hfId = "") {
  const catalog = loadCatalog();
  const text = `${display || ""} ${hfId || ""}`;
  for (const row of catalog.intents) {
    if (row.classify && new RegExp(row.classify, "i").test(text)) return row.id;
  }
  return catalog.fallbackIntent;
}
