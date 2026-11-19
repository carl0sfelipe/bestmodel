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
  silently. Owner decision (2026-11-18): the English posts close on the same
  store link **with an explicit notice that it ships to Brazil only** — the
  stranger in Brazil is still the buyer, the stranger abroad is told the truth
  instead of being sent to a checkout that cannot ship to them.
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
- The English pages carry the store link only with the Brazil-only notice (D2);
  never present `orbe.live` as a purchase path that ships anywhere.

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

---

# Research notes (2026-11-18)

The sources below are the evidence the contract above rests on. Vendor-published
studies (Profound, Weglot, Translated, SarkarSEO, Neuronwriter) are flagged as
such: they sell translation or GEO tooling, so their numbers are directional.

## R1 — Google's rules (primary source)

**Localized versions of your pages** and **Managing multi-regional and
multilingual sites** (developers.google.com/search/docs/specialty/international):

1. `hreflang` is the only explicit signal. Google does not infer the audience
   from the URL or the subdomain — `en.example.com` means nothing to it.
2. Every version must reference the **complete set, including itself**, and the
   annotations must be **reciprocal**.
3. Only one implementation: HTML `<link>`, HTTP `Link` headers or sitemap
   `xhtml:link`. Mixing them for the same URLs creates conflicting signals.
4. `x-default` is the fallback for an unmatched language.
5. **Google identifies the page language from the visible content, not from the
   `lang` attribute and not from the URL.** Clear, consistently written content
   is what makes the detection work.
6. **A template-translated page with the body in the source language is treated
   as a duplicate.** Full translation is the requirement, not cosmetics.
7. **Do not redirect by browser language, and do not adapt by IP.** The reason
   given is not preference: such redirects may prevent users *and crawlers*
   from reaching every version, and IP location is "difficult and generally not
   reliable". **Googlebot generally does not send an `Accept-Language` header**
   — so an automatic switch is, for the crawler, a coin flip.
8. Parameters (`?loc=de`) are "not recommended": hard to segment, hard for
   users to recognize.
9. If the wrong version is shown, the answer is a **visible switcher**, not a
   forced redirect — "show links on all pages for users to select their
   region and/or language of choice". The switcher also exposes the other
   versions to Google.
10. The recommended structures are ccTLD / subdomain / subdirectory. **The
    subdirectory is described as the cheapest to maintain on the same host**;
    the ccTLD as the most unmistakable but costly and restricted. The choice
    is about operation, not about ranking.

**AI Overviews and the generative features** (developers.google.com/search/docs/fundamentals/ai-optimization-guide):

- No special schema, no `llms.txt`, no machine-only block, no ideal length, no
  freshness requirement.
- What matters: indexed and eligible for a snippet, in the generative AI
  features in Search Console, publicly crawlable, semantic HTML (helpful, not
  mandatory), a good page experience, reduced duplicate content.
- The AI features use the **same index** as the ordinary results — there is no
  separate AI index to optimize for.
- "AI systems understand general meaning and synonyms, so the page does not
  need to repeat the user's exact wording" — the long-tail keyword does not
  have to appear verbatim.

**Hreflang implementation (SEOBeni guide, Jul 2026)** — the pitfalls that become
acceptance criteria:

- Absolute HTTPS URLs; ISO 639-1 + ISO 3166-1 Alpha-2 (`en-GB`, never `en-UK`
  or `en-EU`).
- `hreflang` must not point to a redirect, a 404, a `noindex` page or a
  non-canonical URL.
- **Every page in a cluster self-canonicalizes.** Canonicalizing all
  translations to one master conflicts with `hreflang`, and Google may then
  discard the annotations — which removes the translated pages from the index.
- Common errors: missing self-reference, one-way return tags, relative URLs,
  conflicting canonical tags, mixing implementations.
- **Ranking impact: none.** `hreflang` guides *which* version is shown and
  stops the versions competing with each other. It is not a signal of quality.

## R2 — The AEO side (what actually gets cited)

**Profound (vendor), 3.25 billion citations, March 2026, 7 AI systems, 14
countries, prompts filtered to each country's native language:**

- Query language changes *which domains* get cited, how often, and whether
  social content appears — "a force more influential than geography", though
  the effect differs per model.
- The source mix per language is completely different. **For Portuguese
  prompts, Google's AI Overviews pull 65% YouTube, 17% Instagram, 7% Reddit**
  (English: TikTok 3.1%). ChatGPT's social sourcing in every market is
  51–76% Reddit — Reddit is English-first, which is why ChatGPT's non-English
  citation rates fall below the English baseline.
- Practical: measure by market *and* model; do not use one global content and
  distribution strategy.

**arXiv 2604.25707 (GEO measurement framework), 602 controlled prompts across
ChatGPT / Google AI Overview / Perplexity:**

- Language effects are platform-specific: Google cited 11.57 sources for
  English prompts vs 7.53 for Chinese; ChatGPT the opposite (7.77 Chinese vs
  7.03 English). **Do not model language as a global factor — model it per
  platform.**
- **The pages that get cited are "reusable evidence containers": 10.59
  headings on average (vs 0.85 in the bottom quartile), more paragraphs,
  denser lists, and content containing numbers, definitions, comparisons,
  procedures or code.**
- **Q&A formatting alone does not help** (0.0947 mean influence for Q&A pages
  vs 0.1005 for others) — the evidence inside matters, the shape does not.
- Length alone is not the driver; semantic fit and evidence density are.
- Recommendation for multilingual sites: **preserve language-relevant titles,
  metadata, headings and answer units** so each localized page can align
  semantically with its target queries, and prefer modular explanatory sections
  over a monolithic translated page.

**Search Engine Land / Ahrefs (1.2 million AI answers, 18,012 pages):** 44% of
ChatGPT citations come from the **first third** of the content.

**Measured on this site's posts (2026-11-18):** 9 headings and ~1,700 words
per post, the answer in the first paragraph. That is already in the range the
cited pages occupy — so the lever is not the shape, it is the language.

**Neuronwriter (vendor), May 2026 — "does hreflang still matter in the AI
era?":**

- "AI search engines do not route. They synthesize." A generative answer can
  combine an English paper, a German industry blog and a global dataset.
- Therefore `hreflang` matters less for AI answers than for the classic
  results, **but the recommendation is to keep it** — and to win AI citations
  through *entity* clarity: localized terminology, `Organization` with
  `sameAs`, `areaServed`, `knowsLanguage`, and genuinely localized content.
- A generic machine translation without local semantic depth is more likely to
  be ignored.

**How these reconcile (the tension worth naming):** Profound measures that
citation *composition* changes per language; Neuronwriter says the answer may
*synthesize across* languages. Both are true and they point the same way for
this site: the answer engine may pull from several languages, but it pulls
from pages that exist in the language of the question and that are *indexed*
in that language. A page that only exists in Portuguese can be cited in an
English answer as one voice among several — never as the page that answers the
Portuguese question outright. The English version is not a translation of the
marketing; it is the version that gets quoted.

## R3 — What this changes in the contract

1. **R1.5 (new) — the `lang` attribute is for humans and screen readers; the
   language detection is done by the content.** This kills any plan to serve
   English chrome over Portuguese bodies: the page would be a mixed-language
   document, and Google detects the language from what it reads. The two trees
   must be *whole documents* in one language — including the navigation and
   the footer, not only the article body.
2. **R1.10 (new) — the switcher is mandatory, not optional.** Google itself
   prescribes the visible switcher as the answer to a wrong-version visit, and
   it doubles as the mechanism that exposes the other tree to the crawler.
3. **R2 (new) — the post must keep its "evidence container" shape in the
   target language**: the first-paragraph answer (the 35–70 words the factory
   already enforces), the comparison table, the FAQ. The factory's gates are
   the mechanism; the language must not dilute them.
4. **R2 (new) — the factory writes the English posts from the same measured
   facts, not from a translation of the Portuguese post.** A translated page
   reads as a translation; a page written from the facts in the target
   language reads as native — which is what "entity localization" means when
   the entities are models, numbers and units.
5. **R2 (new) — `inLanguage` in the Article schema** (the schema.org field
   that says which language the article is in) and `knowsLanguage` /
   `areaServed` on the Organization, per R2's structured-data recommendation.
6. **R1 (new) — `hreflang` is not a ranking lever.** The acceptance test is
   correctness (reciprocal, self-canonical, no redirect targets, `x-default`
   present), not a metric. The ranking lever is the second language existing
   at all.

## Sources

- Google Search Central — [Localized versions of your pages](https://developers.google.com/search/docs/specialty/international/localized-versions)
- Google Search Central — [Managing multi-regional and multilingual sites](https://developers.google.com/search/docs/specialty/international/managing-multi-regional-sites)
- Google Search Central — [Optimizing your website for generative AI features](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
- Google Search Central community — [General guide to managing an international website](https://support.google.com/webmasters/community-guide/363341479/general-guide-to-managing-an-international-website?hl=en)
- SEOBeni — [Hreflang tags implementation guide 2026](https://seobeni.com/blog/hreflang-tags-implementation-guide-2026/) (vendor)
- Profound — [How query language reshapes AI citations](https://www.tryprofound.com/blog/how-query-language-reshapes-ai-citations) (vendor)
- arXiv — [A measurement framework for generative engine optimization](https://arxiv.org/html/2604.25707v2)
- Search Engine Land — [44% of ChatGPT citations come from the first third of content](https://searchengineland.com/chatgpt-citations-content-study-469483)
- Neuronwriter — [International SEO in the AI era: does hreflang still matter?](https://neuronwriter.com/international-seo-hreflang-ai-era-2026/) (vendor)
- Weglot — [Multilingual GEO study 2026](https://www.weglot.com/blog/multilingual-geo-study-2026) (vendor)
- EZY Research — [Do AI bots read llms.txt?](https://www.ezy.ai/research/do-ai-bots-read-llms-txt)
- Seer Interactive — [Do LLMs respect robots.txt?](https://www.seerinteractive.com/insights/do-llms-respect-robotstxt)
- Optiseon — [Should you implement llms.txt in 2026?](https://optiseon.com/blog/llms-txt-honest-guide-2026/) (vendor)
