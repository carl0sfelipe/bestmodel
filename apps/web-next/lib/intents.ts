import catalog from "../../../packages/intent-catalog/catalog.json";

export type IntentId = (typeof catalog.intents)[number]["id"];

type IntentRow = (typeof catalog.intents)[number];

export const INTENTS: {
  id: IntentId;
  name: string;
  glyph: string;
  desc: string;
  category: IntentId | null;
}[] = catalog.intents.map((row) => ({
  id: row.id,
  name: row.name,
  glyph: row.glyph,
  desc: row.desc,
  category: row.storable ? row.id : null,
}));

export function intentOf(id: string | null | undefined): IntentRow | undefined {
  return catalog.intents.find((row) => row.id === id);
}

export function isMultimodal(id: string | null | undefined): boolean {
  const row = intentOf(id);
  return !!row && row.modality !== "text";
}
