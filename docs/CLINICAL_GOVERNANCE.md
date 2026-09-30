# Clinical Governance

Positioning: **Veterinary clinical reference and decision-support**, not an "AI veterinarian". Audience is veterinary professionals and students.

## Non-negotiables
1. No dose, withdrawal period, contraindication, interaction, price, or registration is published without >= 1 linked Source.
2. Nothing scraped, imported, or AI-extracted is published automatically. It lands in staging and needs human approval.
3. AI never generates or arithmetically computes clinical values. Arithmetic is deterministic code. If no verified data: "Verified information is currently unavailable."
4. Edits to published clinical data create a new revision; history is never overwritten. Audit log records who, what, why, source.
5. Seed/dev data is labeled `DEVELOPMENT DATA - NOT CLINICALLY VERIFIED` in the UI and cannot carry a verified status.

## Verification states
| State | Public? | Meaning |
|---|---|---|
| community_submitted | No | User submission in moderation |
| needs_verification | No | Flagged or unsupported |
| source_found_pending_review | No (admin only) | Source attached, awaiting reviewer |
| manufacturer_supplied | Yes, labeled | From company literature; not independently verified |
| official_regulatory | Yes, labeled | From a regulator/registered label |
| expert_reviewed | Yes, labeled | Checked by a qualified reviewer |
| verified | Yes | Source + qualified veterinarian reviewer approval |
| deprecated / archived | Archived view only | Superseded or withdrawn, kept for history |

Dose records need `verified`, `expert_reviewed`, or `official_regulatory` to feed the calculator. Withdrawal data: only `official_regulatory` or `verified`.

## Roles
Company representatives may submit product/price updates but cannot set clinical statuses. Only Veterinarian Reviewer (and above) can move a clinical record to `verified`/`expert_reviewed`. No self-approval: reviewer != submitter.

## Calculator rules
Show inputs, formula, steps, source, assumptions, reviewed date. Reject impossible values (negative/zero weight, out-of-range species weight, unit mismatch). Warn when result exceeds the sourced maximum dose. Never round in a way that changes the dose by more than the display precision; store full precision.

## Every clinical page shows
Last reviewed date, review status badge, Sources section, and the disclaimer: reference for licensed professionals; not a substitute for clinical judgment or the product label.

## Change control
Dose/withdrawal changes show old vs new, source, reviewer, date. Regulatory withdrawals/alerts can be fast-tracked but still require a source.

## Imported, not reviewed (owner decision, 2026-09-30)
Catalogue records created by an import (generics, companies, products from a public regulator list) carry the status `imported_unverified`. By the owner's decision they are **listed on the public site** (search, drug, product, company and country pages) with a visible "Imported, not reviewed" badge and notice, `noindex` on their pages, and no place in the sitemap. The switch is `SHOW_UNVERIFIED_IMPORTS`.
Limits that do not change: this applies only to catalogue names, never to doses, withdrawal periods, interactions, clinical notes or prices; the assistant and the interaction checker use reviewed records only; an application is never shown as a registration; a reviewer can still promote a record (a public status needs a linked source, sign-off needs a veterinarian reviewer). Legal review of the source's terms is still outstanding (`DATA_SOURCES.md`, `INGESTION.md`).
