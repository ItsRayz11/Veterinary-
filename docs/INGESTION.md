# Ingestion pipeline

Goal: get real catalogue data in through a reviewed, traceable path. Nothing imported is ever public on arrival.

## Flow (implemented, `apps/ingestion`)
1. **Stage.** Staff upload a CSV in the review panel (Imports tab) or via `POST /api/v1/staff/imports/`. Required: country, source title, source URL or publisher, and a **licence/terms note**. The file's SHA-256 is stored; the same file cannot be imported twice for a country.
2. **Match.** Each row is matched to existing records (generic by name/synonym, company by name/alias within the country, product by manufacturer + brand). Invalid rows (missing fields, unknown registration status) and duplicates (existing brand, existing registration number) are flagged, not created.
3. **Approve or reject.** A staff member approves rows one by one, or approves all clean pending rows. Approval creates missing Generic / Company / Product / Registration rows as `needs_verification` and links every created row to the import's Source. Rejection needs a reason. Every action writes an audit entry.
4. **Review.** Records appear in the normal Review queue. Only the governed workflow (source required, vet reviewer for sign-off, no self-approval) can make them public.

## CSV format
Header names are case-insensitive; common aliases (`brand`, `product`, `generic`, `company`, `reg_no`) are accepted.

| Column | Required | Notes |
|---|---|---|
| `brand_name` | yes | |
| `generic_name` | yes | reuses an existing generic when the normalised name or a synonym matches |
| `manufacturer` | yes | company in the batch's country |
| `registration_number` | no | unique per country |
| `registration_status` | no | `registered`, `expired`, `suspended`, `withdrawn`, `unknown` |

Limits: 2 MB, 5000 rows per file. Strengths, packs and ingredients are not imported; add them in the admin.

## What is deliberately not done
- No fetcher pulls from DRAP, CDSCO or any site. The per-source checklist in `DATA_SOURCES.md` (terms, robots.txt, API/bulk access, scope, legal sign-off) is still unfilled for every source, so none is enabled.
- The importer does not decide that a record is correct; it only records where it came from.
- Prices and doses are not imported here. They have their own governed models.

## Per-source status
| Source | Terms checked | robots.txt | Bulk/API | Scope | Legal sign-off | Enabled |
|---|---|---|---|---|---|---|
| DRAP product database | no | no | no | unknown (vet vs human) | no | no |
| DRAP veterinary application lists | no | no | no | applications, not registrations | no | no |
| CDSCO veterinary approvals | no | no | no | unknown | no | no |
| openFDA / DailyMed animal labels | no | no | API exists (unconfirmed terms) | US only | no | no |
