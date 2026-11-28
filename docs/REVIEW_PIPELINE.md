# Review pipeline: sources, grouping, images (R2), bulk actions

## Why records said "No source linked"
Importers (universities) stored a plain `source_url` on the record but never created the `Source`
and `SourceLink` rows the review workflow reads. A URL string is evidence, a `Source` is the
registry entity. `apps/sources/linking.py` now creates, matches (by canonical URL and publisher
identity), validates and links them. Original URL fields are never modified.

## Flow (task `review-pipeline`, idempotent, time-boxed to Vercel's 30 s)
dedupe sources -> for new/changed/stale records: link sources, find images -> probe link health ->
store eligible images in R2 -> assess (group facets, completeness, duplicates, change detection,
recommendation). `universities-sync` imports one country per run. Neither task changes a record's
review status.

Schedules (`api/vercel.json`): `universities-sync` 05:30 (several countries per run), `review-pipeline` 06:00, `staff-digest` 07:00 UTC daily (see `AUTOMATION_PLAN.md`).
Elsewhere: `python manage.py run_task review-pipeline`. Admin "Run pipeline now" also works.
Existing data: `python manage.py backfill_sources` (also run in the production build).

## Publication rules
- `safe_batch` only means "a reviewer may approve this in a bulk action". Requirements: low-risk
  kind (universities), source with verified provenance + open licence + working link, >= 80 %
  complete, no duplicate candidates, no conflicts, not development data.
- Bulk approval goes through `set_review_status` (linked non-invalid source, veterinarian
  reviewer/admin only, no self-approval) and is re-checked per record at execution time.
- Drugs, doses, clinical, education: never `safe_batch`. Regulator catalogue records stay under
  the DataSource tiers in `PUBLICATION_TIERS.md`. Per CLAUDE.md, scraped data is never published
  without review, so nothing publishes unattended.

## Images / Cloudflare R2
Only https images with an open licence (and credit + file page for CC BY) are copied; raster
JPEG/PNG/WebP/GIF only, <= 5 MB, verified by magic bytes. Keys are content-addressed
(`images/<sha[:2]>/<sha>.<ext>`), duplicates stored once; credit, licence and source URLs are
stored as object metadata. Server variables (never sent to the browser):
`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_BASE_URL`
(optional `R2_ENDPOINT`). Web: `NEXT_PUBLIC_R2_PUBLIC_HOST` (hostname of the public base URL) so
`/_next/image` can proxy previews. Until configured, images stay `pending`.

## Admin
"Pipeline & backlog" section: dashboard, search, grouping (action, issue, type, country, provider,
batch, status, source, image, trust, completeness), bulk actions with preview, chunked progress,
retry and audit. The review modal is now a workspace (data, sources, images/R2, checks,
duplicates, history, approve / request correction / reject).
