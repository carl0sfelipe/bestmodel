import type { MetadataRoute } from "next";
import { loadDerived } from "../lib/engine";
export default function sitemap(): MetadataRoute.Sitemap { const base = "https://bestmodel.run"; return ["", "/hardware", "/wall", "/claims", "/submit", "/track-record", "/mural", "/console", ...loadDerived().models.map((model) => `/m/${model.slug}`)].map((path) => ({ url: `${base}${path}`, lastModified: new Date("2026-08-30T04:43:50.758Z") })); }
