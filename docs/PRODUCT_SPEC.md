# Product Spec

**Veterinary Intelligence Platform**: clinical reference, pharmaceutical intelligence, education, and opportunities for veterinary professionals. Pakistan first, India second, country-agnostic architecture.

## Audiences
Vet students (DVM/BVSc), veterinarians, researchers, vet pharma companies/distributors, livestock/poultry professionals, job and scholarship seekers. Not paravets/farmers as primary users.

## Core navigation graph (the product)
Generic -> Products (brands) -> Manufacturer -> Manufacturer's other products; Generic -> Species dose -> Calculator; Product -> Pack -> Price -> Price history; Generic/Product -> Country availability -> Sources. Education (Subject -> Topic -> MCQs) links to the same drug entities.

## Information architecture (URLs)
`/` search-first home; `/drugs/[slug]`; `/products/[slug]`; `/companies/[slug]`; `/species/[slug]`; `/calculators/[name]`; `/study/[subject]`; `/questions/[subject]`; `/jobs/[country]`; `/scholarships`; `/news`; `/sources`. Only pages with real structured content are indexable (no thin programmatic pages).

## Page composition
- Generic: compact summary header, tabs (Overview, Dosing by species, Safety, Brands, Availability, Sources), species selector, brand table.
- Product: header (brand, manufacturer, generic, form, strength), packs+prices, country-specific label info, withdrawal table, sources.
- Company: header, product catalog (filter by generic/country), markets.
- Home: global search, clinical tools, popular drugs, latest regulatory items, jobs, scholarships. Not overcrowded.

## UX principles
Mobile-first, dense but readable tables (horizontal-scroll or stacked on phones), bottom nav, sticky search, accessible calculator inputs, no decorative animation, no lorem ipsum, restrained clinical visual style. Design tokens defined in Phase 1.

## Phase scope
Phases 0-14 as in the master prompt; ordered by ROADMAP.md. First shippable slice ("walking skeleton"): Country/Species/Company/Generic/Product schema -> admin CRUD -> generic and product pages -> dose calculator on manually reviewed seed data.

## Seed data policy
Development seeds are clearly labeled and cannot be `verified`. Real Pakistan data arrives in Phase 6 through the reviewed ingestion pipeline.

## Open items
- Competitor analysis (Plumb's, VIN, Drugs.com vet, VetScraft, regional apps): needs hands-on review.
- Owner decisions: hosting budget, domain/brand name (working title "VetRef"), who the qualified veterinarian reviewers are (governance depends on this).
- Legal review of DRAP/CDSCO bulk-data reuse.
