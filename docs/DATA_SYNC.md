# Data synchronisation

## Sources
| Source | Status | Licence / terms | Notes |
|---|---|---|---|
| UK VMD Product Information Database (XML, 5,300+ current products) | importer live; target species per authorisation, status, expired detection | Open Government Licence v3.0, stated on the VMD page (checked 2026-11-04) | `uk_vmd.py`; attribution shown on pages that use it |
| Health Canada DPD | importer exists, terms not yet confirmed | reported OGL-Canada; confirm on the dataset page | enable in Admin after reading terms |
| FDA Green Book / openFDA | not importable yet | to be checked; the adverse-event dataset is not an approved-product list and must not be used as one | needs a Green Book adapter |
| EMA veterinary UPD | not importable | API access needs registration with EMA | adapter to be written once credentials exist |
| DRAP (Pakistan) | imported once from public lists | no reuse licence stated; internal review only | |
| GBIF / WOAH | not integrated | taxonomy and educational references only, never doses or authorisations | |

## Running
- Scheduled: GitHub Actions `Data source sync` (daily 06:00 UTC) runs `manage.py sync_data_sources` then `--alert`; it needs the repo secrets `DATABASE_URL` and `SECRET_KEY` and the repo variable `DATA_SYNC_ENABLED=true`. A failing or stale source fails the run, and GitHub emails the owner.
- Vercel Cron keeps only the cheap reachability checks (`/api/v1/cron/data-sources/`); a full import is too long for a 30 s function.
- Manual: `python manage.py sync_data_sources --source uk-vmd-pid --force`; Admin > Data sources has "Check selected sources now".
- A source needs `import_enabled` and confirmed terms. Everything imported is "Imported, not reviewed".

## Safety properties
- Idempotent: re-running changes nothing (rows are matched by registration number; files by checksum).
- Target species belong to the authorisation, never the ingredient. Unmapped wording ("Honey bees") is kept as text.
- Status changes (registered → expired) are applied only to unreviewed records, and audit-logged with the old value; reviewed records are counted for a person to look at.
- A failed download, an unreadable layout or an empty file stops the run; nothing is deleted.

## Rollback
1. `python manage.py rollback_import --source uk-vmd-pid --since YYYY-MM-DD` previews; add `--apply` to remove unreviewed records created since then and restore status changes. Reviewed records are kept.
2. For anything else restore the Neon snapshot or use point-in-time restore (6 h history on the current plan).
