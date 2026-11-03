# UI / UX / SEO enhancement checklist

Tracks the website-wide enhancement brief. `[x]` done and verified, `[ ]` open.

## Design system and components
- [x] Semantic tone tokens (teal, blue, green, violet, amber, red) with dark mode
- [x] Central icon system (Lucide) with category mapping (`ui/icons.tsx`)
- [x] Calculator line illustrations (`ui/calc-art.tsx`)
- [x] Flag component with safe fallback (`ui/flag.tsx`)
- [x] FeatureCard, CalculatorCard, DocumentCard, CountryHero, SectionHeader, MetadataBadge (`ui/visual.tsx`)
- [ ] ProductImageFallback (category SVG) for products
- [ ] EmptyState illustration variant
- [ ] RelatedResources component (evidence-based links only)

## Pages
- [x] Homepage, calculators index and detail, countries index and detail, species index and detail
- [x] Study hub, past papers, jobs and scholarships index, primary and mobile nav icons
- [ ] Drug detail (`/drugs/[slug]`), product detail (`/products/[slug]`), product table
- [ ] Drug classes (`/classes`), companies (`/companies/[slug]`)
- [ ] Search page and search box suggestions (icons, grouping, keyboard)
- [ ] Jobs and scholarships detail pages
- [ ] Lessons, books, flashcards, interactions, ask, auth pages
- [ ] Disease and university pages: no routes exist in the app, nothing to enhance (record in recommendations)

## Text clutter
- [ ] Shorten verbose subtitles and CTAs; keep crawlable content

## Navigation and discovery
- [x] Breadcrumb JSON-LD
- [ ] Breadcrumbs on every nested public page
- [ ] Related links species to medicines, drug to calculators, country to products

## SEO
- [x] Country meta descriptions
- [ ] Unique titles and descriptions on every public route
- [ ] Product/drug structured data where source data supports it
- [ ] Noindex for parameterised duplicates (search results)
- [ ] Sitemap includes companies and products as appropriate

## Quality
- [x] Typecheck, lint, tests, build, desktop browser check
- [ ] Mobile width check (390px) and horizontal overflow check
- [ ] Reduced-motion, focus states, contrast of tone tokens
- [ ] Final cross-check for bugs, regressions and disconnections

## Recommendations needing external assets
- Licensed species photos, India/country map outlines from verified boundary data, product packaging images, university imagery
