# L09 — Multilingual SEO/AEO (one domain, two languages, explicit)

> Decision source: owner request 2026-11-18 ("para vender no Brasil preciso ranquear
> as perguntas em português, mas para o site do bestmodel deveria ser tudo em inglês
> quando é acessado por um gringo"). Research: Google Search Central
> "Localized versions of your pages" + "Optimizing your website for generative AI
> features on Google Search"; vendor GEO studies (Nov 2026) for the citation-language
> behaviour — the vendor statistics are flagged as such in the study.
>
> Context: the measurement pool is language-neutral (models, numbers, units). The
> commercial path is Brazilian (Orbe ships the Mac mini M6). The audience is global.
> The conflict is only in the blog: 23 posts written in pt-BR are served from an
> English site.

## Objective

One canonical host serves two languages with an explicit contract — every page
declares its language, every translation pair is mutually linked with `hreflang`
plus `x-default`, each version self-canonicalizes, and the per-page `<html lang>`
matches the content. A Brazilian query lands on the Brazilian page; an English
query lands on the English page; an answer engine asked in Portuguese cites the
Portuguese page, asked in English cites the English one.

## Verified state (2026-11-18, measured in this repo)

1. `apps/web-next/app/layout.tsx` hardcodes `<html lang="en">` for every route.
2. The site chrome is English (masthead, nav, footer). `/transparencia` is
   English; `/planejar` is Portuguese ("Quantos tok/s você tira do rig antes de
   alugar") — one Portuguese route inside an English index.
3. `apps/web-next/content/blog/*.mdx` (23 posts) are pt-BR. Their frontmatter has
   `title, slug, description, date, author, coverImage, coverStats` — no `lang`.
4. `apps/web-next/app/blog/page.tsx` metadata is English ("Measured local-AI
   notes: which model fits a GPU, how fast, and how to add a signed run") while
   every post it lists is Portuguese.
5. `app/blog/[slug]/page.tsx` sets `alternates: { canonical }` only. There is no
   `hreflang`, no `alternates.languages`, and no `inLanguage` in the Article
   schema anywhere in `apps/web-next`.
6. `app/sitemap.ts` lists URLs without language alternates.
7. `llms.txt` exists at the repo root and is English; it is not part of the
   language contract (see Rules).

## Decisions

- **D1 — URL architecture: one domain, language by path.** English at the root
  (`/blog/<slug>`), Portuguese under `/pt` (`/pt/blog/<slug>`). Rationale: one
  host keeps the measurement authority, the links and the brand in a single
  domain; Google's own guidance leaves the structure free (separate domain,
  subdomain or subfolder) but requires the `hreflang` values to be explicit,
  because the audience is not inferred from the URL. A subdomain (`pt.…`) is
  explicitly not inferred by Google, so it buys nothing over a path. The 23
  Portuguese URLs move once, one day after publication, before they are indexed.
- **D2 — The English offer.** The Portuguese posts close on `orbe.live`, which
  ships in Brazil only. An English post cannot carry that call to action
  honestly. Default for this spec: the English posts close on the CLI ("measure
  your own machine") and drop the store link. Owner may substitute another offer.
- **D3 — No automatic redirect.** No IP-based, `Accept-Language`-based or
  cookie-based redirect between the two language trees. Redirects make one
  version invisible to the crawler that never matches, and the AI crawlers
  (GPTBot, Perplexity) are not Brazilian — a Portuguese page that only a
  Brazilian browser can reach is a page no answer engine can cite. `x-default`
  is the fallback instead.

## Contract

1. **Per-page language.** Every blog frontmatter carries `lang: "pt-BR"` or
   `lang: "en"`. The publisher (content factory) writes it; the site reads it.
   The `<html lang>` of a page equals its `lang` — set through the locale
   (middleware header or a route group with its own root layout), not by
   per-request guessing.
2. **`hreflang` pairs.** Each page emits `alternates.languages` with its own
   language and its pair, plus `x-default` on the English tree. The pair is
   reciprocal (A declares B, B declares A) and each page canonicalizes to
   itself — a translated version must never canonicalize to the other language,
   or the translated page leaves the index.
3. **Article `inLanguage`.** The Article schema of each post carries the same
   language code as the frontmatter.
4. **Indexes split.** `/blog` lists the English posts, `/pt/blog` lists the
   Portuguese ones. Each index declares its own language in `<html lang>`, in
   its metadata and in its canonical. A language switcher links the two trees
   page by page (and the two indexes at the root).
5. **Sitemap.** `app/sitemap.ts` lists both trees, each URL with its language
   alternates (one implementation only: the sitemap carries the `xhtml:link`
   entries, mirroring the per-page `hreflang`).
6. **Factory can write the second language.** The content factory writes the
   English posts from the same measured facts: the writer prompt already takes
   the language from the tenant (`idioma`), the facts are language-neutral, and
   the measured methods are the only Portuguese input the writer sees. The
   English question set is the Portuguese one translated (the H1 is the question
   verbatim, so the question itself must be in the target language).
7. **The answer block survives translation.** The first paragraph stays the
   extractable answer (35–70 words, one fact) in both languages — that is the
   block an AI Overview quotes. The Portuguese contract stays as it is.

## Rules

- Never redirect by geography, browser language or cookie (D3).
- Never canonicalize one language version to the other.
- Never ship a translated page whose body is still the source language:
  Google treats template-translated pages as duplicates, so the English post
  must be English all the way down (title, description, body, FAQ, frontmatter).
- Never invent a number, metric or claim to fill a translation gap — the
  measurement pool and the honesty ladder stay as they are.
- `llms.txt` is not a lever here: the strongest available measurement (83 sites,
  Jul 2026) found near-zero fetches by the major AI crawlers (OpenAI 7 fetches,
  Perplexity 0). The file stays as it is; the effort goes into the pages.
- The English pages must not carry the Brazilian store call to action without
  the owner's decision (D2).

## Acceptance

```bash
# 1. every post declares a language, and the pairs are reciprocal
node --experimental-strip-types --test apps/web-next/lib/**/*.test.ts
node apps/web-next/scripts/check-i18n.mjs        # new: fails on a missing/unpaired/inconsistent language

# 2. the rendered page's <html lang> equals the post language
curl -s https://www.bestmodel.run/pt/blog/<pt-slug> | grep -o '<html lang="[^"]*"'   # pt-BR
curl -s https://www.bestmodel.run/blog/<en-slug>   | grep -o '<html lang="[^"]*"'   # en

# 3. hreflang is reciprocal and x-default is present
curl -s https://www.bestmodel.run/blog/<en-slug> | grep -o 'hreflang="[^"]*"' | sort -u
curl -s https://www.bestmodel.run/pt/blog/<pt-slug> | grep -o 'hreflang="[^"]*"' | sort -u

# 4. the site still builds and the copy gate is clean
cd apps/web-next && npm run build && bash scripts/slop-gate.sh
```

## Out of scope

- `llms.txt` as an AI-visibility lever (see Rules).
- A third language, a country-level variant (`pt-PT`), or an English regional
  split.
- Machine translation of the measurement pool (the facts stay as measured).
