# Publication tiers, source governance and indexing

Owner-approved 2026-11-14. This extends the existing review gate (`CLINICAL_GOVERNANCE.md`); it does not replace it.

## Three classifications (derived from `review_status`, never stored twice)
| Tier | Statuses | Meaning shown to visitors |
|---|---|---|
| Official regulatory listing | `official_regulatory` | Regulator facts (name, company, authorisation number, status). **Not clinically reviewed.** |
| Clinically reviewed | `expert_reviewed`, `verified` | A qualified person signed off (existing workflow). |
| Pending / unverified | everything else (incl. `imported_unverified`) | Not eligible for publication. Hidden. |

`manufacturer_supplied` stays a separate, labelled public tier. Registration **applications** (DRAP lists) carry `Product.listing_kind = application` and are shown as "Application, not an approval".

The factual tier can only ever touch `Generic`, `Company`, `Product`, `ProductRegistration` (`automation/publishing.py::FACTUAL_MODELS`, asserted in tests). Doses, withdrawal periods, contraindications, interactions and treatment advice are never published by it and never become verified automatically.

## Source governance (per `DataSource`)
States (`publication_state`): monitor only, 1 confirm terms, 2 approve field mapping, 3 approve first batch, then `approved_manual` or `auto_publishing` (admin switch `auto_publish`).
- Staging imports always create hidden `imported_unverified` rows and tag each registration with its feed and `last_checked_at`.
- "Check staged records" shows validation (valid / rejected + reasons). "Approve first batch" publishes the valid rows as official listings and needs regulator name + attribution text.
- After that, each sync publishes valid new rows and follows regulator status changes for rows of the same source.
- **Held for a person** (nothing applied): file shrinks > `max_removal_pct`, grows > `max_growth_pct`, > 25% unreadable entries (layout change). Admin "Release held sync" accepts once.
- **Left unchanged and logged** (`source_inconsistency`): same registration number now with a different brand.
- Changes to clinically reviewed rows are never made silently.
- All steps write `AuditLog` entries.

## Public provenance
Every registration shows regulator, jurisdiction, regulatory status, source link, last checked date, clinical-review state and the licence attribution (`provenance` in the product API, `ProvenanceList` in the web app).

## Country indexing
`Country.index_mode` (auto/never/always), `index_min_registrations` (default 300), `index_min_provenance_pct` (default 95). A page is `indexable` if clinically reviewed, or an official listing registered in an indexable country. Non-indexable pages stay reachable, get `noindex` and are left out of the sitemap. Report: admin panel > Country coverage, `GET /api/v1/staff/country-coverage/`.

## Search
Zero-result searches are counted (normalised text + counter only, no user data; `SearchMiss`). Admin panel > Failed searches. Matching covers generic, synonym, ingredient, brand and company, ignores form/strength/salt words, falls back to typo suggestions, popular generics and countries.

## Advertising (off by default)
Server env: `ADS_ENABLED=true`, `ADSENSE_CLIENT=ca-pub-…`, optional `ADSENSE_SLOT_DIRECTORY|EDUCATION|BLOG|JOBS`. Needs a redeploy. Adds AdSense origins to the CSP only when enabled, serves `/ads.txt`, asks consent before loading anything, labels every slot "Advertisement". There is no clinical or regulatory ad zone, so ads cannot be placed beside doses, withdrawal, interactions, registrations or calculators.

## Sources
- UK VMD Product Information Database: OGL v3.0 stated on the VMD page (checked 2026-11-14). No attribution wording on the page; we show the standard OGL attribution.
- Health Canada Drug Product Database: Open Government Licence - Canada v2.0, monthly updates (checked 2026-11-14).
- US DailyMed animal labels (`us-dailymed`): listing facts only, US labelling. DailyMed terms still **unconfirmed**; import stays off.
