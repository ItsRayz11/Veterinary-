# Data Sources & Licensing Strategy

Status: initial research (2026-09-30). Everything below is a **candidate**. Terms, robots.txt, and data format must be checked per source before any fetcher is written; results recorded in the checklist at the bottom. "Not yet verified" means exactly that.

## Principles
- Prefer official downloads/APIs over scraping HTML. Respect robots.txt, ToS, rate limits.
- Store link + minimal structured facts (names, reg numbers, dates), not copyrighted full text/PDFs.
- Every fetched item records `source_url, fetched_at, checksum, license_note`.
- Facts (a registration number, a brand name) are generally not copyrightable, but database rights and ToS may still restrict bulk reuse; get legal review before mass import.

## Pakistan (priority 1)
| Source | Use | Notes |
|---|---|---|
| DRAP registered product database ([eapp.dra.gov.pk/WebProductIndex.php](https://eapp.dra.gov.pk/WebProductIndex.php), [DRAP database update notice](https://www.dra.gov.pk/news_updates/regulatory_updates/updated-database-of-pharmaceutical-and-biological-drug-product/)) | Registered products: name, dosage form, composition, reg no., date, holder, manufacturer | Search interface; unclear if human-drugs only or includes veterinary. **Verify scope and bulk-access terms.** |
| DRAP veterinary application lists ([e-services page](https://www.dra.gov.pk/e-services/online-data-verification/applications-for-pharmaceutical-drugs/)) | Search results indicate a veterinary applications spreadsheet and veterinary biologics list. | Applications are not registrations; do not treat as approved. Not yet verified by opening the file. |
| DRAP regulatory notices / alerts | Recalls, withdrawals | Link out, store summary |
| Livestock depts, UVAS, PMAS-AAUR, other vet universities, PVMC | Curricula, past-paper indexes, job/scholarship notices | Link to source; no rehosting |
| Manufacturer sites/product literature | Label info, pack sizes | Tag `manufacturer_supplied`; check each site's terms |

## India (priority 2)
| Source | Use | Notes |
|---|---|---|
| CDSCO veterinary drugs & vaccines approvals ([vet-data-2020-to-2022.pdf](https://cdsco.gov.in/opencms/export/sites/CDSCO_WEB/Pdf-documents/vet-data-2020-to-2022.pdf), [CDSCO approvals](https://cdsco.gov.in/opencms/opencms/en/Approval_new/)) | Approved veterinary drug/vaccine lists (name, strength, form) | PDFs; needs table extraction + manual review. Coverage/completeness not yet verified. |
| Veterinary Council of India, DAHD, ICAR, state vet universities | Education, jobs, notifications | Link out |

## International references (for clinical content and API-friendly data)
| Source | Use | Notes |
|---|---|---|
| FDA CVM / [openFDA animal & veterinary](https://open.fda.gov/apis/animalandveterinary/), [DailyMed](https://www.dailymed.nlm.nih.gov/) animal labels | Approved labels incl. dose, withdrawal (US context), adverse events | US government data, generally reusable, but **country-specific**: a US withdrawal time must never be shown as a Pakistan one. Confirm openFDA terms page. |
| EMA veterinary (Union Product Database, EPARs) | EU labels, MRLs | Verify reuse policy |
| Open-access journals, WHO/FAO/WOAH, Codex MRLs | Citations, background | Respect each license (CC-BY etc.) |

Textbooks (e.g. Plumb's, Merck Vet Manual) are copyrighted: cite as references only; never ingest text without a license.

## Per-source verification checklist (must be filled before building each fetcher)
- [ ] ToS read; commercial reuse allowed? (Y/N/unclear)
- [ ] robots.txt allows path
- [ ] Official API or bulk download exists
- [ ] Data fields available; update frequency
- [ ] Scope confirmed (veterinary vs human)
- [ ] Legal sign-off for bulk storage

Sources: DRAP portal, CDSCO, openFDA and DailyMed as linked above.
