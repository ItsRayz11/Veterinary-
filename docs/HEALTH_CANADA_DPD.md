# Health Canada Drug Product Database (DPD): veterinary adapter

Status: adapter built and tested; **import stays disabled** (`import_enabled=False`, terms unconfirmed).
Checked 2026-11-14. Nothing here was run against production data.

## Findings from the official sources

| Item | Result |
|---|---|
| Bulk extract page | Reachable. ZIPs on `www.canada.ca/content/dam/hc-sc/documents/services/drug-product-database/`: `allfiles.zip` (marketed), `allfiles_ap` (approved), `allfiles_dr` (dormant), `allfiles_ia` (cancelled). Per-table zips exist too. Page shows "Last Updated 2026-11-02"; no update schedule is stated. |
| Data layout page | Reachable. UTF-8 text, comma separated, double-quote delimited; header row not stated. `vet.txt` = veterinary species, `route.txt`, `form.txt`, `status.txt`, `comp.txt`, `ingred.txt`, all keyed on `DRUG_CODE`. |
| API documentation (`health-products.canada.ca/api/documentation/...`) | **Unreachable** from our tooling (`ECONNREFUSED`). Endpoints, rate limits and fields are unverified. The adapter does not use the API. |
| `health-products.canada.ca/robots.txt` | **Unreachable** (`ECONNREFUSED`); not assumed permissive. |
| `www.canada.ca/robots.txt` | Reachable; no rule matches the DPD ZIP path, no crawl-delay. |
| Licence | The extract page does **not** name the Open Government Licence. It says only "see the Drug Product Database Terms and Conditions" (`healthycanadians.gc.ca/important-eng.php#a6`), which we have **not** read. OGL-Canada v2.0 itself permits commercial use and redistribution with attribution ("Contains information licensed under the Open Government Licence – Canada"), but it is unconfirmed that it governs this dataset. |

## Open blockers (a person must clear these)

1. Read the DPD Terms and Conditions page and confirm which licence governs the extract; if unclear, ask Health Canada (`hc.osip.sys-bppi.sc@canada.ca`, listed as the DPD contact). Then use "Confirm terms" in the admin.
2. The seeded `ca-health-canada-dpd` row (migration 0007) says the OGL is "stated on the dataset page (checked 2026-11-14)". The official extract page does not say that. The note should be corrected, and `data_url` should point to the official `canada.ca` `allfiles.zip`, once a person approves editing that production row (not changed here).
3. Date formats, and the full list of `CLASS` values, are not documented; the adapter keeps date text as given and filters on `CLASS == "Veterinary"` only. Verify against a real extract.
4. The extract is cancelled/dormant-split across `_ia`/`_dr` files; the sync downloads `allfiles.zip` (marketed) only. Decide whether to ingest cancelled/dormant products.
5. API access and `health-products.canada.ca` robots rules are unverified. Retry from another network if the API is ever needed.

## What the adapter does (`api/apps/ingestion/adapters/ca_dpd.py`)

- Keeps CLASS = Veterinary only; joins drug, companies, ingredients, status, species, routes and forms on `DRUG_CODE`.
- Preserves the source status text and its date, the DRUG_CODE, the DIN (as registration number) and the record's last-update date, in `notes`.
- Species/routes/forms are source text; none inferred. Strengths are not parsed. No doses, indications or withdrawal times are read.
- Rejects unusable archives (not a zip, missing core files, wrong layout, no veterinary rows) with `ExtractError`.
- Skips and counts duplicates (DRUG_CODE, DIN) and incomplete rows; unmapped statuses become `unknown`.
- Accepts header rows and `_ap`/`_dr`/`_ia` file names.
- Pipeline: staged as unreviewed, never public; reruns are idempotent by batch checksum. Downloads retry 5xx/429/network errors twice with backoff (`datasources._download`).

## UK VMD

The VMD adapter now also records the regulator's `VMDProductNo` in the notes of each row. Review and publication gates are unchanged.
