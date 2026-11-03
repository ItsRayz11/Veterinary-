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

## Recommendations needing external assets
- Licensed species photos, India/country map outlines from verified boundary data, product packaging images, university imagery

- Backend list endpoints for products and companies, so the sitemap can include them
- Disease and university sections do not exist as routes; add them with reviewed data before designing visuals for them
- Verified-only product images: wire into `ProductArt` once a source and licence are recorded
