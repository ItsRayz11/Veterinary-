# Architecture

## Decision: Django API + Next.js frontend (monorepo)

The repo currently holds only a `create-next-app` scaffold plus an older `PLAN.md` proposing Next.js + Drizzle + Neon (TypeScript only). The master prompt prefers Django. **Decision: follow the prompt (Django/DRF/Postgres/Celery), keep Next.js as the frontend.**

Why Django wins for this product:
- Admin, review queues, moderation, and audit are core (prompt §29, §44). Django admin + permissions give a working admin on day one.
- Ingestion pipelines (fetch -> parse -> normalize -> match -> review) need background workers; Celery is mature.
- Clinical entities need constraints, versioning, and migrations that Django's ORM handles well.
- Calculation engine stays a pure, dependency-free module. Clinical results are computed server-side in Python (authoritative) and mirrored client-side in TypeScript for offline/instant UX; a shared JSON test-vector file keeps both identical.

Trade-off: two runtimes to deploy. Accepted.

```
/
  web/        Next.js (App Router, TS, Tailwind), SSR/ISR public pages, PWA
  api/        Django + DRF
    apps/     accounts core countries species companies pharma clinical
              calculators pricing regulatory education jobs scholarships
              sources ingestion search moderation
  docs/
  infra/      docker-compose (postgres, redis), deployment notes
```
Apps start minimal; `exams`, `notifications`, `analytics` fold into `education` / `core` until they justify separation.

## Layering rules
- `models.py` data + constraints only. `services.py` business logic. `selectors.py` read queries (prefetch, no N+1). `api/` serializers/views thin. `calculators` has no Django imports.
- Ingestion never writes to published tables; it writes to `ingestion.StagedRecord`. Publishing goes through a reviewed service call.
- Country, species, and unit are data, never code branches. No `if country == "PK"` in logic.

## Key cross-cutting mechanisms
- **Provenance:** every clinical row has FK(s) to `sources.Source` (many-to-many with page/quote locator). No source, no publish.
- **Verification state machine:** field `review_status` on clinical rows (see CLINICAL_GOVERNANCE.md). Only `published` states are served publicly.
- **Versioning/audit:** clinical models use append-only revisions (django-simple-history or equivalent) plus an explicit `AuditLog` for admin actions.
- **Units:** canonical unit table + conversion in one module; free text units are rejected on clinical/calculation fields.
- **Search:** Postgres FTS + `pg_trgm` + synonym table; behind a `search` service interface so Meilisearch/Typesense can replace it later.

## Infrastructure (to confirm in Phase 1)
- DB: Neon Postgres (branching helps migration testing). Requires pooled connection strings and `pg_trgm` enabled.
- Web: Vercel. API + Celery worker + Redis: needs an always-on host (Railway/Fly/Render paid tier). Free tiers that sleep are rejected because workers and scheduled ingestion cannot sleep. Final pick after cost comparison in Phase 1.
- Media: Cloudinary, later. Secrets: env vars only; `.env*` git-ignored.

## Next.js note
This is Next 16 with breaking changes vs. older versions. Before writing frontend code, read the matching guide in `web/node_modules/next/dist/docs/` (see AGENTS.md).
