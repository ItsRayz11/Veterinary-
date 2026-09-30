# Ingestion pipeline

Goal: get real catalogue data in through a reviewed, traceable path. Nothing imported is ever public on arrival.

## Flow (implemented, `apps/ingestion`)
1. **Stage.** Staff upload a CSV in the review panel (Imports tab) or via `POST /api/v1/staff/imports/`. Required: country, source title, source URL or publisher, and a **licence/terms note**. The file's SHA-256 is stored; the same file cannot be imported twice for a country.
2. **Match.** Each row is matched to existing records (generic by name/synonym, company by name/alias within the country, product by manufacturer + brand). Invalid rows (missing fields, unknown registration status) and duplicates (existing brand, existing registration number) are flagged, not created.
3. **Approve or reject.** A staff member approves rows one by one, or approves clean pending rows 50 at a time (repeat until none remain; flagged rows are marked duplicate/invalid and leave the pending list). Approval creates missing Generic / Company / Product / Registration rows as `needs_verification` and links every created row to the import's Source. Rejection needs a reason. Every action writes an audit entry.
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
- No fetcher pulls from DRAP, CDSCO or any site. Files that a person (or this project's owner) downloaded from a public download link are imported with `manage.py import_products <adapter> <file> --country XX --source-title ... --publisher ... --url ... --license-note ...` (adapters: `standard`, `drap-vet-applications`, `drap-vet-biologicals`). It resumes by file checksum, can run in parallel with `--shard i/n`, and always creates unreviewed, hidden records.
- DRAP's online product registry carries a notice that it must not be used as a reference, so it is not scraped. The per-source checklist in `DATA_SOURCES.md` (terms, robots.txt, API/bulk access, scope, legal sign-off) is still unfilled for every source, so none is enabled.
- The importer does not decide that a record is correct; it only records where it came from.
- Prices and doses are not imported here. They have their own governed models.

## Per-source status
| Source | Terms checked | robots.txt | Bulk/API | Scope | Legal sign-off | Enabled |
|---|---|---|---|---|---|---|
| DRAP product database | no | no | no | unknown (vet vs human) | no | no |
| DRAP veterinary application lists | downloaded as public CSV files; no reuse licence stated | n/a (direct file links) | files | applications, not registrations | **no: legal review needed before any public release** | imported 2026-09-30 for internal review only (420 veterinary + 102 biologicals applications, hidden) |
| CDSCO veterinary approvals | no | site unreachable from the build machine | PDFs | unknown | no | no (files to be supplied by a person) |
| openFDA / DailyMed animal labels | no | no | API exists (unconfirmed terms) | US only | no | no |

## India (and any other country)
The pipeline is country-agnostic: the country is chosen per import and every rule (duplicates, registration numbers, currency, availability) is data-driven. India is already in the reference data (INR, CDSCO / DAHD).
Suggested workflow for CDSCO's published veterinary approval lists (PDF tables, `DATA_SOURCES.md`):
1. A person checks the CDSCO terms and records the outcome in the per-source table above. Nothing is fetched automatically.
2. Extract the table to CSV with the columns above (a spreadsheet or a PDF table tool), then spot-check rows against the PDF.
3. Import through the Imports tab with the CDSCO document as the source and its licence/terms note.
4. Review and approve as for any other country; records stay unreviewed until the review workflow promotes them.
Approvals in the PDFs are approvals, not proof a product is on sale; do not mark availability beyond what the document states.
