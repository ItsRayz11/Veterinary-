# UI / UX / SEO enhancement checklist

Tracks the website-wide enhancement brief. `[x]` done and verified, `[ ]` open.

## Design system and components
- [x] Semantic tone tokens (teal, blue, green, violet, amber, red) with dark mode
- [x] Central icon system (Lucide) with category mapping (`ui/icons.tsx`)
- [x] Calculator line illustrations (`ui/calc-art.tsx`)
- [x] Flag component with safe fallback (`ui/flag.tsx`)
- [x] FeatureCard, CalculatorCard, DocumentCard, CountryHero, SectionHeader, MetadataBadge (`ui/visual.tsx`)
- [x] ProductImageFallback (category SVG) for products
- [x] EmptyState illustration variant
- [x] RelatedResources component (evidence-based links only)

## Pages
- [x] Homepage, calculators index and detail, countries index and detail, species index and detail
- [x] Study hub, past papers, jobs and scholarships index, primary and mobile nav icons
- [x] Drug detail (`/drugs/[slug]`), product detail (`/products/[slug]`)
- [x] Drug classes (`/classes`), companies (`/companies/[slug]`)
- [x] Search page and search box suggestions (icons, grouping, keyboard)
- [x] Jobs and scholarships detail pages
- [x] Lessons, books, flashcards, interactions, ask, auth pages
- [x] Disease and university pages: no such routes exist in the app yet, so nothing to enhance (see recommendations)

## Text clutter
- [x] Cards carry title + one line; long explanations stay on detail pages (crawlable text kept)

## Navigation and discovery
- [x] Breadcrumb JSON-LD
- [x] Breadcrumbs on every nested public page
- [x] Related links species to medicines, drug to calculators, country to products

## SEO
- [x] Country meta descriptions
- [x] Unique titles and descriptions on every public route
- [x] Product/drug structured data: already present (Drug, Organization JSON-LD, only for reviewed records)
- [x] Noindex for parameterised duplicates (search results)
- [x] Sitemap reviewed: API has no product/company list endpoint, so only drugs, species, classes, countries, lessons and listings are listed

## Quality
- [x] Typecheck, lint, tests, build, desktop browser check
- [x] Mobile width check (390px) and horizontal overflow check
- [x] Reduced-motion, focus states, contrast of tone tokens
- [x] Final cross-check for bugs, regressions and disconnections

## Real assets and data (added after the first pass)
- [x] Real flags: `flag-icons` (MIT), all 271 SVGs in `web/public/flags`, built by `web/scripts/build-country-assets.mjs`
- [x] Country outlines from Natural Earth (public domain) in `web/public/maps`, shown on country pages
- [x] Species photographs from Wikimedia Commons, open licences only, credits in `web/src/lib/image-credits.json` (`web/scripts/fetch_species_images.py`)
- [x] Universities: `apps/universities` model, API, `import_universities` command (Wikipedia + Wikidata, imported-unreviewed), pages `/universities`, `/universities/[slug]`
- [x] Open-licence university images with per-image credit; `/credits` page lists every source and licence
- [x] API list endpoints for products and companies; sitemap now includes reviewed products, companies and universities

## Still open (needs external data or a decision)
- Product packaging photos: no source with a licence that allows reuse; products keep the category illustration
- Production data: run `python manage.py migrate` then `python manage.py import_universities` on the deployed database
- Coverage: Wikipedia categories list only some schools (none for the UAE). Add missing schools in the admin, or extend `UNIVERSITY_SOURCES` in `apps/core/reference_data.py`
- Records stay "Imported, not reviewed" (noindex, excluded from the sitemap) until an editor reviews them
- Country flags for new countries need no code: add the country, the flag file already exists
