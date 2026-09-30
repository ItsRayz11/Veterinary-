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
- [x] Postgres: Neon (Postgres 18) connected via `DATABASE_URL`; all 29 migrations applied, reference data seeded
- [ ] pg_trgm/FTS search on Postgres; CI Postgres service container (see DEPLOYMENT.md)
- [x] Auth endpoints (session-based register/login/logout/me, throttled, no self-assigned privileged roles) + role permission classes
- [x] Admin foundation: Django admin, user role admin, immutable AuditLog
- [ ] CI: `.github/workflows/ci.yml` written but never run (no GitHub remote yet)
- [x] Tooling: ruff, pytest(-django), eslint, prettier, vitest, typecheck (all passing locally)
- [x] Logging + uniform API error envelope + `/api/v1/health/`
- [x] Design tokens (light/dark) + first component (StatusBadge)
- [x] Base UI kit (part): alerts, breadcrumbs, data table, section nav, empty/error/not-found states, search UI, app shell with skip link + mobile bottom nav
- [x] Base UI kit (remaining): buttons, form controls, skeleton, modal (`ui/forms.tsx`, `ui/modal.tsx`)
- [x] Login/register/account pages, header auth menu, CSRF-aware browser API client (verified through the Next proxy: register, session, /auth/me)
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
- [x] Reviewer UI with old-vs-new diff view: staff review panel `/admin-panel` (review queue with governed status change + history diff, price moderation, question reports, admin audit log); API `apps.staff` (8 tests). Roles enforced server-side.
- [ ] Public references section per page (needs Phase 4 API)

## Phase 4: Drug Encyclopedia UI
- [x] Public read API: generics, products, companies, countries, species, grouped search (accent/case-insensitive, synonyms, did-you-mean)
- [x] Search: global box with live results + /search page
- [x] Generic page: summary, sections nav, species-filtered dosing table, safety, brands table (country filter), sources
- [x] Product page: composition/strengths, packs, country availability, withdrawal (strict), sources
- [x] Company page: catalogue + generic portfolio; navigation both ways (generic -> brand -> company -> products)
- [x] Review status + "development data" shown on every record; empty states say verified info is unavailable
- [x] Species pages (`/species`, `/species/[slug]`: only generics with public doses), country landing pages (`/countries/[iso2]`: reviewed registrations only), drug-class browse (`/classes`); API `pharma/browse.py` with 4 tests
- [ ] Typo tolerance on Postgres (pg_trgm) and brand-name fuzzy match; current fuzzy covers generics only
- [x] SEO (part): `robots.txt`, dynamic `sitemap.xml` (public records only, tolerant of API downtime), canonical URLs, API-backed index pages render on request so a build never needs the API
- [ ] SEO (remaining): JSON-LD, OG images (Phase 14 audit)
- [ ] Manual mobile/browser QA (only HTTP-level checks done so far)

## Phase 5: Calculators
- [x] Pure engines in Python (authoritative) and TypeScript (instant UI), identical results via shared hand-computed vectors (`shared/calc-vectors.json`)
- [x] mg/kg, mg->mL, mL->mg, % -> mg/mL, dilution, dehydration deficit, daily fluid, infusion rate, drip rate, CRI, drinking-water flock dose, withdrawal end date
- [x] Input validation, formula + steps exposed, max-dose warning (never clips), exact decimals
- [x] API endpoint with function whitelist
- [x] Dose calculator page (weight lb/kg, mg/mL or %, prefill link from calculator-ready doses only)
- [x] UI pages for the other calculators (dilution, dehydration, daily fluids, infusion, drip, CRI, flock water, withdrawal date): registry-driven, TS engine, hand-computed tests; no clinical defaults
- [ ] Guided flow: pick species -> generic -> indication -> product strength (needs verified data, Phase 6)
- [ ] Medication schedule / reminders (needs user accounts UI)

## Review log
- Phases 1-5 post-commit review (graphify dependency graph + manual read): no import cycles; core abstractions are Generic/Product/ReviewStatus as intended. Found and fixed: (1) auth throttle was a silent no-op, (2) unreviewed registrations leaked into product pages and country lists. Both now covered by tests.
- Known, deferred: fuzzy search loads all generic names on a miss (fine at small scale; replace with pg_trgm on Postgres); `docs/API.md` and `INGESTION.md` not written yet (`DEPLOYMENT.md`, `TESTING.md` now exist).

## Phase 6: Pakistan Data
- [x] Reviewed ingestion pipeline (`apps/ingestion`, `docs/INGESTION.md`): CSV stage -> match (generic/company/product/registration, duplicates, errors) -> staff approve/reject -> unreviewed records linked to the Source; checksum + licence note required; audit log; admin + Imports tab in the review panel; 6 tests; verified live (imports stay hidden until reviewed)
- [ ] Real Pakistan data: blocked on per-source terms/legal sign-off (checklist in `INGESTION.md` all unfilled); no fetcher enabled; nothing invented
- [ ] Strength/pack/ingredient import (add via admin for now)
## Phase 7: Pricing
- [x] PriceRecord: append-only, per pack x country x region x city x price type, currency, source (required unless user-submitted), confidence, verified_at; DB constraints
- [x] Price history + current price selectors; public API `/products/<slug>/prices/`
- [x] User submissions (new price / report incorrect) via authenticated, throttled endpoint; never public until approved
- [x] Moderation service: moderator/admin only, no self-approval, reason required to reject, audit log; accepted report unpublishes disputed price but keeps history
- [x] Admin approve/reject actions; price table on product page with source, location, last-checked
- [x] Submission/report forms on the product page (suggest price / report incorrect; goes to moderation; verified live: submission reaches staff queue, self-approval blocked). Fixed CSRF-token rotation after login in the browser client
- [x] Price analytics (`pricing/analytics.py`, 6 tests): change and % vs previous (exact decimals, half-up), min/max, region comparison; never mixes currency, price type, pack or location; unpublished excluded. Product page shows trend line (SVG + data table) and regional table; verified live with fictional local prices

## Phase 8: Education
- [x] Subject > Topic (optional link to a generic), structured MCQ Question + Options (DB: max one correct option), difficulty, country/exam/university/year/source
- [x] Publishing rule: question needs source, >= 2 options and exactly one correct option before it can go public
- [x] Filters: subject, topic, university, exam, country, year, difficulty
- [x] Mock exams of 20/50/100 questions: random from filtered pool, answers hidden until submit, scoring, per-topic breakdown, weak topics, history
- [x] Answer validation (option must belong to its question; users can only see their own exams)
- [x] Bookmarks (toggle), question error reports, past-paper index (links to legal sources only, licence note required)
- [x] Admin: options inline, governed publish actions, readiness check
- [x] Web UI: study hub (filters, exam start, history), exam runner (one question at a time, navigator, unanswered warning), results (topic breakdown, weak topics, review with bookmark/report), past-paper index. Pages load; full exam flow covered by API tests only (no questions exist to click through)
- [ ] Real question content and past-paper index entries (none exist; nothing invented)
- [x] Flashcards (Leitner boxes 1-5, server-scheduled, hand-computed tests), lessons (source + reviewer required to go public), book references (cited only), progress-over-time chart with per-subject accuracy and weak topics; admin + governed review; 8 tests. No content exists, so pages show honest empty states

## Phase 9: Jobs + Scholarships
- [x] Jobs and scholarships (`apps/opportunities`, 7 tests): user/staff submissions, moderator approval (no self-approval, reason to reject, audit log), original apply link required (http/https only), automatic expiry (closing date or 90 days), search/filters, 5-pending cap per user, throttled submit/report, 3 distinct user reports send a live listing back to moderation
- [x] Web: /jobs, /scholarships (+ detail, submit forms, report button), moderation tab in the review panel, sitemap entries; verified live end to end with fictional local data
- [ ] Notifications/alerts for new listings (needs email provider decision)
- [ ] Company-verified employer accounts (needs owner decision on verification process)
## Phase 10: Automation
- [x] Hardened outbound HTTP (`automation/safe_http.py`): public http(s) hosts only, ports 80/443, every redirect re-validated, size/time caps, robots.txt honoured; SSRF cases tested (loopback, private, link-local, IPv6, file/ftp)
- [x] Link-health checker for Source URLs (robots-aware, HEAD then GET, failures tracked, broken sources listed for staff); verified live against the network
- [x] Feed ingestion (RSS/Atom via defusedxml, entity bombs rejected): feeds are staff-registered, disabled by default, need a licence note, re-check robots each run (auto-disable if refused), items become PENDING listings for moderation only, deduped by URL, unchanged feeds skipped
- [x] Scheduler: `/api/v1/cron/<task>/` (Bearer `CRON_SECRET`, constant-time compare, disabled when unset), Vercel cron schedule in `api/vercel.json`, `manage.py run_task`, JobRun audit trail, admin "run now", Automation tab (20 + 1 tests)
- [ ] No feed is registered yet (needs verified sources); Redis/worker queue deferred (not needed at this scale)
- [ ] Known limit: DNS rebinding between validation and connect (documented; only staff-registered URLs are fetched)
## Phase 11: India
- [x] Country-agnostic proof: found and removed the one hardcoded `["PK","IN"]` (drug page country filter, now driven by `/countries/`); permanent guard test scans 250+ source files for country literals (would have caught it); parity tests run import, registration, country page and price currency for PK, IN and US through the same code
- [x] India in reference data (INR, CDSCO/DAHD); import workflow for CDSCO lists documented in `INGESTION.md`
- [ ] Real CDSCO data: needs a person to check terms and extract the PDF tables (not automated, not fetched)
- [ ] Regional-language UI (Hindi/Urdu) and India-specific units/label conventions: not started (needs translation resources)
## Phase 12: AI Intelligence
## Phase 13: PWA + Performance
## Phase 14: Production Hardening

(Phases 2-14 get task-level checklists when they start, per the continuity rule. Scope per phase is defined in `PRODUCT_SPEC.md`.)
