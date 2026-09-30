# Roadmap

Single source of truth for progress. Only tick a box when the work is implemented **and** verified.
Priority order: Accuracy > Data integrity > Safety > Architecture > Usability > Performance > Automation > SEO > Polish > Monetization.

## Phase 0: Research & Architecture
- [x] Inspect repository (fresh `create-next-app` scaffold, no commits, no backend)
- [x] Reconcile old `PLAN.md` with master prompt (superseded by this file)
- [x] Data-source analysis: Pakistan / India / international (`DATA_SOURCES.md`)
- [x] Licensing strategy (`DATA_SOURCES.md`)
- [x] Clinical governance rules (`CLINICAL_GOVERNANCE.md`)
- [x] Product spec / information architecture (`PRODUCT_SPEC.md`)
- [x] Architecture + stack decision (`ARCHITECTURE.md`)
- [x] ERD / data model (`DATA_MODEL.md`)
- [ ] Competitor analysis (deferred: needs live review of Plumb's, Vetscraft, VIN, Drugs.com Vet, etc.; tracked in `PRODUCT_SPEC.md` §Open items)
- [ ] Verify each source's terms/robots.txt individually before any fetcher is written (per-source checklist in `DATA_SOURCES.md`)
- [ ] Design system plan (tokens, components), done at start of Phase 1 with the UI scaffold
- [ ] Owner sign-off on stack decision (Django + Next.js) and monorepo layout

## Phase 1: Engineering Foundation
- [x] Move Next.js scaffold to `web/`
- [x] Django project in `api/` (Python 3.12 venv, settings from env, custom User model with roles)
- [ ] Postgres: Neon project + `DATABASE_URL`, pg_trgm; currently SQLite fallback only (no Docker on this machine)
- [x] Auth endpoints (session-based register/login/logout/me, throttled, no self-assigned privileged roles) + role permission classes
- [x] Admin foundation: Django admin, user role admin, immutable AuditLog
- [ ] CI: `.github/workflows/ci.yml` written but never run (no GitHub remote yet)
- [x] Tooling: ruff, pytest(-django), eslint, prettier, vitest, typecheck (all passing locally)
- [x] Logging + uniform API error envelope + `/api/v1/health/`
- [x] Design tokens (light/dark) + first component (StatusBadge)
- [x] Base UI kit (part): alerts, breadcrumbs, data table, section nav, empty/error/not-found states, search UI, app shell with skip link + mobile bottom nav
- [ ] Base UI kit (remaining): buttons, form controls, skeleton/loading states, modal
- [x] Web -> API client (server `apiGet`, same-origin `/api/v1` rewrite for browser code)

## Phase 2: Core Pharmaceutical Database
- [x] Country (jurisdiction) model
- [x] Species model (hierarchical, e.g. broiler under poultry)
- [x] Units table with conversion (canonical units)
- [x] Company (+ aliases, roles, duplicate constraint per country)
- [x] Generic, Ingredient (many-to-many, so combinations work), synonyms, drug class tree
- [x] Product/brand (many per generic, many per company), ingredient strengths, dosage forms, pack sizes
- [x] Country availability (ProductRegistration, unique per country + reg number)
- [x] Review status gate (`public()` queryset), dev-data cannot be verified (DB constraint), history on catalogue models
- [x] Admin for all of the above, reference + fictional dev seed commands, selectors with prefetch
- [x] Tests (19 passing): relationships, duplicates, constraints, idempotent seed, unit conversion, query count

## Phase 3: Clinical Knowledge
- [x] Sources + SourceLink (any row -> many sources, with page/locator)
- [x] Indication, Route, Commodity lookups
- [x] DoseRegimen: structured (min/max, dose-rate unit, interval, duration, max dose), DB check constraints
- [x] WithdrawalPeriod: product x country x species x commodity x route, unique, stricter public rule (regulatory/verified only)
- [x] ClinicalNote (contraindication, precaution, adverse effect, toxicity, warning) and ordered-pair Interaction
- [x] Verification workflow (`apps.core.review.set_review_status`): source required, only vet reviewer/admin can sign off, no self-approval, dev data never signed off, audit entry per change
- [x] Admin: status read-only in forms, changes via governed bulk actions; history via simple-history
- [x] Calculator gate: `DoseRegimen.objects.calculator_ready()` (verified / expert reviewed / official only)
- [ ] Reviewer UI with old-vs-new diff view (history data exists; UI in Phase 10 review queue)
- [ ] Public references section per page (needs Phase 4 API)

## Phase 4: Drug Encyclopedia UI
- [x] Public read API: generics, products, companies, countries, species, grouped search (accent/case-insensitive, synonyms, did-you-mean)
- [x] Search: global box with live results + /search page
- [x] Generic page: summary, sections nav, species-filtered dosing table, safety, brands table (country filter), sources
- [x] Product page: composition/strengths, packs, country availability, withdrawal (strict), sources
- [x] Company page: catalogue + generic portfolio; navigation both ways (generic -> brand -> company -> products)
- [x] Review status + "development data" shown on every record; empty states say verified info is unavailable
- [ ] Species pages (`/species/[slug]`), country landing pages, medicine categories (drug class browse)
- [ ] Typo tolerance on Postgres (pg_trgm) and brand-name fuzzy match; current fuzzy covers generics only
- [ ] SEO: sitemap, robots, JSON-LD, OG images (Phase 14 audit)
- [ ] Manual mobile/browser QA (only HTTP-level checks done so far)

## Phase 5: Calculators
- [x] Pure engines in Python (authoritative) and TypeScript (instant UI), identical results via shared hand-computed vectors (`shared/calc-vectors.json`)
- [x] mg/kg, mg->mL, mL->mg, % -> mg/mL, dilution, dehydration deficit, daily fluid, infusion rate, drip rate, CRI, drinking-water flock dose, withdrawal end date
- [x] Input validation, formula + steps exposed, max-dose warning (never clips), exact decimals
- [x] API endpoint with function whitelist
- [x] Dose calculator page (weight lb/kg, mg/mL or %, prefill link from calculator-ready doses only)
- [ ] UI pages for the other calculators (dilution, fluids, drip, CRI, flock, withdrawal date)
- [ ] Guided flow: pick species -> generic -> indication -> product strength (needs verified data, Phase 6)
- [ ] Medication schedule / reminders (needs user accounts UI)

## Review log
- Phases 1-5 post-commit review (graphify dependency graph + manual read): no import cycles; core abstractions are Generic/Product/ReviewStatus as intended. Found and fixed: (1) auth throttle was a silent no-op, (2) unreviewed registrations leaked into product pages and country lists. Both now covered by tests.
- Known, deferred: fuzzy search loads all generic names on a miss (fine at small scale; replace with pg_trgm on Postgres); `docs/API.md`, `INGESTION.md`, `DEPLOYMENT.md`, `TESTING.md` not written yet.

## Phase 6: Pakistan Data
## Phase 7: Pricing
- [x] PriceRecord: append-only, per pack x country x region x city x price type, currency, source (required unless user-submitted), confidence, verified_at; DB constraints
- [x] Price history + current price selectors; public API `/products/<slug>/prices/`
- [x] User submissions (new price / report incorrect) via authenticated, throttled endpoint; never public until approved
- [x] Moderation service: moderator/admin only, no self-approval, reason required to reject, audit log; accepted report unpublishes disputed price but keeps history
- [x] Admin approve/reject actions; price table on product page with source, location, last-checked
- [ ] Submission/report forms in the web UI (needs login/register screens)
- [ ] Price charts + analytics (increase/decrease, region comparison)

## Phase 8: Education
## Phase 9: Jobs + Scholarships
## Phase 10: Automation
## Phase 11: India
## Phase 12: AI Intelligence
## Phase 13: PWA + Performance
## Phase 14: Production Hardening

(Phases 2-14 get task-level checklists when they start, per the continuity rule. Scope per phase is defined in `PRODUCT_SPEC.md`.)
