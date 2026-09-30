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

## Final review (phases 6-14)
A high-effort code review of everything since the last push, plus a manual pass, found and fixed:
- **Assistant number check bypass (safety):** numbers with a glued unit (`500mg`, `2.5mg/kg`) were not checked, and spelled-out numbers / fractions were ignored. Now digits with or without units, number words and fraction characters must all appear in the records; 12 bypass tests. A stray control character in a regex (from script escaping) was found and removed; the tree was scanned for others (none).
- **Link check on Postgres:** `NULLS FIRST` was database-dependent, so never-checked sources could starve; explicit ordering + rotation test. **30 s function limit:** per-probe timeout, 12 s budget, per-host robots cache, stale-run cleanup; feeds share the budget.
- **Atom feeds:** the posting link was overwritten by enclosure/replies links; only `alternate` is used.
- **Reports carried over** after a moderator re-approved a listing; now cleared (and audited) on approval.
- **Import form** threw after a successful upload (`currentTarget` after `await`); **flashcards** lost the whole session on one failed save; **interaction checker** could show a stale "nothing recorded" result for a different drug list; **service worker** showed "offline" on a slow but working network; **admin link** ignored `ADMIN_URL`.
- **Import scale (manual finding):** ~4 queries per row to stage and ~25 to approve would time out on a 5,000-row file. Staging is now ~20 queries for any size (in-memory matcher, agreement test), approval is chunked (50/click) and flagged rows leave the pending list.
- **Throttle identity (second review + manual):** trusting `X-Forwarded-For` let clients pick their own bucket, and behind proxies everyone shares one address. Replaced with a shared-secret scheme: the web proxy (`src/proxy.ts`) forwards the real client IP with `WEB_PROXY_SECRET`, the API believes it only when the secret matches and otherwise ignores forwarding headers; browser-sent copies are stripped. Verified through the real proxy (client A limited, B not, header injection and direct spoofing still limited).

**Second review round** (after the fixes above) found and I fixed: the number check still skipped `.25 mg/kg`, `q8h`, `x3` (every digit run now counts); the fetch layer let `ValueError`/`HTTPException` escape and had no per-probe deadline (all failures are `FetchError`, 8 s per source, one bad source or feed no longer aborts or starves a run); an open redirect via `/\evil.com` in the login `next` parameter (URL-parser based `safeNext`, 20 cases); the interaction checker could show a stale failure or spin forever on 403; the service worker served a 5xx instead of a saved copy; the admin path was baked into the public bundle (now delivered to staff by the API); drug-class list counts ignored sub-classes; assistant retrieval scanned every drug and brand per question (now indexed lookups, fixed query count).
- Real-browser end-to-end runs: calculators, offline, login/logout, admin panel, CSP (all passing).

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
- [x] Deterministic interaction checker (`/interactions`, API `/interactions/check/`): reviewed interactions only, severity-sorted, sources, explicit "no result is not safe" note
- [x] Grounded assistant (`apps/assistant`, `/ask`), 21 tests with a fake model: only reviewed records are retrieved; no record -> the model is never called; answer must be JSON citing only provided records; every number must appear in those records (invented/computed doses are discarded); failures return just the related records; prompt-injection test; login required, throttled (20/h), every question and outcome logged for audit; disabled without `ANTHROPIC_API_KEY`
- [ ] Real-model path untested: no API key here (set `ANTHROPIC_API_KEY`, optional `ASSISTANT_MODEL`, default `claude-opus-5-5`); review the first answers in the Django admin (AssistantLog) before promoting it
- [ ] Not started: semantic/vector search, OCR/label extraction, AI-drafted content (all would need the same reviewed-record gate)
- [x] CI fixed to run without `api/.env` (DEBUG/SECRET_KEY env; verified locally with `.env` hidden, 162 tests); Postgres job added as informational (`continue-on-error`) until first seen green
## Phase 13: PWA + Performance
- [x] Installable PWA: manifest (name, standalone, theme colours, maskable icon, shortcuts), stdlib-generated icons (`web/scripts/make-icons.py`), apple-touch icon, theme-color meta; verified in a production build (manifest, icons, `sw.js` served with `no-cache`)
- [x] Service worker (`public/sw.js`): public reference pages and calculators available offline (calculators precached with their JS chunks), static assets cache-first, network-first navigation with an offline page, bounded cache; never touches `/api/`, accounts, admin, exams, flashcards, assistant or auth pages. 16 tests run the real worker in a sandbox; a deliberate mutation (removing `/account` from the deny list) was caught
- [x] Query-budget guards on 13 public endpoints + growth tests (`core/tests/test_query_budget.py`). The growth test found a real N+1 (drug page re-fetched the generic once per brand: 13 -> 23 queries); fixed in `brands_for_generic`, count now flat
- [ ] Not verified on real devices/browsers: installability prompt, Lighthouse scores, offline behaviour in an actual browser (only unit-tested + HTTP-level)
- [ ] Web push notifications (needs VAPID keys + subscription store + an email/notification decision); background sync
- [ ] API-level HTTP caching headers/CDN rules and image optimisation (no images yet)
## Phase 14: Production Hardening
- [x] Audits run and recorded: `pip-audit` and `npm audit` clean; secrets scan of working tree + full git history clean (no keys, tokens or connection strings; `.env` never tracked); `manage.py check --deploy` clean (2 HSTS advisories deliberately silenced, owner decision); OpenAPI schema warning-free with 63 unique operations (`--fail-on-warn` test)
- [x] Django: HttpOnly CSRF cookie (client fetches the token from the body), SameSite Lax, request size limits, configurable `ADMIN_URL`, HSTS opt-ins via env; 8 hardening tests
- [x] Web: CSP (no remote scripts, `frame-ancestors 'none'`), nosniff, frame deny, referrer/permissions/COOP, HSTS; verified in a production build and in real Chrome (0 CSP violations, pages hydrate)
- [x] Accessibility (automated part): WCAG AA contrast test of every text/background token pair in light and dark themes (fails when a token is broken, checked by mutation); tables have captions, forms have labels, skip link, focus and aria-live regions exist from earlier phases
- [x] Real-browser end-to-end check (`web/scripts/browser-check.mjs`, 13 checks): calculators compute under the CSP, service worker precaches, calculators work with the server truly stopped, private pages never cached
- [x] Docs: `SECURITY.md` (controls, gaps, owner decisions), `RUNBOOK.md` (first deploy, backups/restore, rotation, incidents), `API.md`, `TESTING.md`; CI runs the deploy check
- [ ] Not done, needs owner decisions or a test environment: staff two-factor auth, per-account lockout, error monitoring/log drain, WAF, Postgres search (`pg_trgm`, needs a Postgres test DB), first green CI run and Postgres job, penetration test, full manual screen-reader/mobile QA, HSTS preload

(Phases 2-14 get task-level checklists when they start, per the continuity rule. Scope per phase is defined in `PRODUCT_SPEC.md`.)
