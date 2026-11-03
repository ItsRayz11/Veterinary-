# Real data resources (research, 2026-11-03)

Candidate sources for the pending "real data" items. **Nothing here is imported.** Per
[INGESTION.md](INGESTION.md) and the project rules, each source needs its terms checked by a person,
a licence note recorded on the import, and every record reviewed before it goes public.

"Reachable" = an HTTP request from the dev machine on 2026-11-03 succeeded. "Licence" is what search
results said; confirm on the source's own page before importing.

## Ready to use (open licence, structured, reachable)

| Source | What it gives | Licence (to confirm) | Notes |
| --- | --- | --- | --- |
| [UK VMD Product Information Database](https://www.vmd.defra.gov.uk/ProductInformationDatabase/) | Authorised UK veterinary medicines: products, actives, species, withdrawal periods, holders; Excel and XML snapshots | Open Government Licence v3.0 (stated on the VMD site) | Best fit for brand, product, ingredient and withdrawal data. Older copies on [data.gov.uk](https://www.data.gov.uk/dataset/authorisations-for-veterinary-medicines) are from 2017; use the VMD page. The separate authorisation-holder address dataset shows "No Licence Provided": do not use it |
| [FDA Green Book](https://www.fda.gov/animal-veterinary/products/approved-animal-drug-products-green-book) | US-approved animal drug products, sponsors, species, withdrawal notes; full monthly refresh | US federal work (confirm on FDA's page) | Also on [data.gov](https://catalog.data.gov/dataset/approved-animal-drug-products-green-book) |
| [openFDA animal and veterinary adverse events](https://open.fda.gov/apis/animalandveterinary/event) | Adverse event reports by species and drug via JSON API | CC0 per [openFDA licence page](https://open.fda.gov/license) (page dated 2014: re-check) | Quarterly updates; reports lag 3-6 months. Signals, not dosing guidance: show as "reported events", never as proof of causation |
| [Health Canada Drug Product Database](https://open.canada.ca/data/en/dataset/bf55e42a-63cb-4556-bfd8-44f26e5a36fe) | Human and veterinary products, ingredients, forms, routes in downloadable files and an API | Open Government Licence - Canada (secondary sources; confirm on the dataset page) | Filter to veterinary rows |
| [APVMA PubCRIS (Australia)](https://data.gov.au/data/dataset/apvma-pubcris-dataset-for-registered-agricultural-and-veterinary-chemical-products-and-approved-acti) | Registered veterinary chemical products and approved actives; CSV/JSON/XML and API, updated weekly | CC BY 3.0 AU (needs attribution) | Page returned 403 to a script: download in a browser or check the API terms |
| [DailyMed animal labels](https://dailymed.nlm.nih.gov/dailymed/spl-resources.cfm) | Full SPL label XML for animal drugs (indications, dosage, warnings) | Not confirmed public domain: check the DailyMed policy page | Labels are manufacturer text, so import as `MANUFACTURER_SUPPLIED`, never `VERIFIED` |

## Target countries (needs a person)

| Source | State | What to do |
| --- | --- | --- |
| **Pakistan, DRAP** [registry search](https://eapp.dra.gov.pk/WebProductIndex.php) and [applications lists](https://www.dra.gov.pk/?p=31571) | Reachable. The 420 + 102 applications are already imported (hidden). The registry carries a disclaimer that it must not be used as a reference for research, citation or statistics | Get DRAP's written permission before treating registry rows as registrations. DRAP also posts [veterinary recall alerts](https://www.dra.gov.pk/wp-content/uploads/2025/10/84.-Recall-alert-Veterinary.pdf) (PDFs): good for a manually reviewed safety feed |
| **India, CDSCO** [Veterinary-Drug-Data-30.06.2026.pdf](https://www.cdsco.gov.in/opencms/export/sites/CDSCO_WEB/Pdf-documents/Veterinary-Drug-Data-30.06.2026.pdf) ("approved 1969 to 30-06-2026") | **Not reachable from the dev machine** (connection fails, as the roadmap noted). The URL is real per search results | Download it in a browser, save it outside git, then build a PDF-table adapter and import through the staged pipeline. Period lists of veterinary drugs and vaccines are also posted on cdsco.gov.in |
| India, DAHD / [NANDI portal](https://www.india.gov.in/noc-approvals-new-drugs-and-inoculation-system-nandi-portal) | Application portal, not a dataset | Not a data source |
| India open data (AIKOSH, data.gov.in) | Only district-level veterinary dispensaries, hospitals, sub-centres (Open Government Licence - India) | Useful for a future "find a clinic" feature, not drugs |

## Not usable as-is

- **EMA Union Product Database (EU):** public site is browse-only. The [UPD access policy](https://www.ema.europa.eu/en/documents/other/union-product-database-upd-access-policy-veterinary-medicinal-products_en.pdf) (rev. 2026) sets access levels; no bulk download or reuse licence was found. Ask EMA before any bulk use.
- **FARAD withdrawal-interval guidance:** USDA-funded and public at farad.org, but no reuse terms were found. Link out; do not copy.
- **Exam questions:** no openly licensed veterinary question bank exists. NAVLE items belong to the NBVME and prep banks are proprietary. Options: reviewer-authored originals, a university that grants a licence, or open textbooks ([Virginia Tech open veterinary guide](https://guides.lib.vt.edu/oer/vetmed): e.g. Veterinary Preventive Medicine CC BY-NC, Veterinary Histology CC BY-SA) as lesson sources, checking each licence (NC blocks monetisation).

## Suggested order

1. UK VMD (largest structured set with withdrawal periods) through the existing CSV import, as unreviewed records.
2. Health Canada and APVMA for broader ingredient and product coverage.
3. openFDA adverse events as a clearly labelled "reported events" panel.
4. CDSCO PDF once downloaded by a person; DRAP permission request in parallel.

Every import: record the source URL, licence and retrieval date; keep records unreviewed until a vet reviewer signs off; keep attribution where required (CC BY, OGL).
