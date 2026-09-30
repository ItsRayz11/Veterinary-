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
- [ ] Base UI kit: buttons, inputs, tables, tabs, alerts, breadcrumbs, skeletons, empty/error states, search UI, app shell with mobile bottom nav
- [ ] Web -> API client + env config

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
- [ ] Sources, indications, dosing, routes, contraindications, interactions, adverse effects, withdrawal, verification, versioning

## Phase 4: Drug Encyclopedia UI
## Phase 5: Calculators
## Phase 6: Pakistan Data
## Phase 7: Pricing
## Phase 8: Education
## Phase 9: Jobs + Scholarships
## Phase 10: Automation
## Phase 11: India
## Phase 12: AI Intelligence
## Phase 13: PWA + Performance
## Phase 14: Production Hardening

(Phases 2-14 get task-level checklists when they start, per the continuity rule. Scope per phase is defined in `PRODUCT_SPEC.md`.)
