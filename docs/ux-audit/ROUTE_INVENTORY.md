# Route inventory: `/drugs`, `/companies`, `/products`

Question from Phase 1: are the 404s on these bare paths a bug, or intended? Recommendation only.
No pages were created, and slug routing, clinical data and eligibility rules are untouched.

## Finding: intentionally absent (by documented design), not a defect

| Evidence | Source |
| --- | --- |
| The product spec lists only `/drugs/[slug]`, `/products/[slug]`, `/companies/[slug]` and states "Only pages with real structured content are indexable (no thin programmatic pages)". | `docs/PRODUCT_SPEC.md` line 12 |
| Discovery is designed around search plus browse pages that do exist: `/classes`, `/species`, `/countries`, and the search-first home. | `docs/ROADMAP.md` line 67; `web/src/app/page.tsx` |
| The sitemap lists slug pages only (public, reviewed records) and none of the three bare paths. | `web/src/app/sitemap.ts` |
| No component links to the bare paths. The drug breadcrumb renders "Drugs" as plain text on purpose. | grep of `web/src` |
| Each of the three directories contains only `[slug]/`. | `web/src/app/{drugs,products,companies}` |

## What an index page would and would not do

**Would help**
- Users who trim a URL or follow a breadcrumb up one level currently reach a 404.
- Crawlers and users get an alphabetical or filtered entry point to the catalogue.

**Risks and costs**
- **Thin or duplicate content.** A flat list of every generic or brand is the "thin programmatic page" the product spec rules out, and duplicates what search and `/classes` already provide.
- **Clinical governance.** Lists must show only reviewed, public records. Unreviewed imports (for example the DRAP applications, which are "unreviewed, hidden" per the roadmap) must never appear. Any index needs the same `unverified` filtering the sitemap applies, plus the status labelling rules in `docs/CLINICAL_GOVERNANCE.md`.
- **Scale.** `/products` could become very large (the roadmap records 420 + 102 imported applications, currently hidden and unreviewed, that could become public as they are reviewed); it needs pagination and filtering, not a single page.
- **Maintenance.** Another set of pages to keep consistent with search ranking and country scoping.

## SEO observations

1. **Structured data gap (verify, do not assume).** Drug, product and company pages emit a `BreadcrumbList` whose middle item ("Drugs", "Products", "Companies") has no `item` URL (`web/src/components/ui/primitives.tsx`, `Breadcrumbs`). Google's breadcrumb documentation, as I understand it, expects an `item` URL for every entry except the last. I did not run the Rich Results Test, so treat this as a likely warning that needs confirming.
2. **404s on bare paths are harmless to ranking** because nothing links to them and they are not in the sitemap. They only matter for users who edit URLs by hand.
3. A bare-path index would add crawlable pages, so it should only ship if it carries real content (descriptions, counts, filters), not a bare list.

## Recommendation (needs a product decision, no change made)

1. **Do not create three flat index pages now.** They conflict with the stated "no thin pages" rule and need governance filtering.
2. **Cheapest fix for the user problem:** make the bare paths useful without new content by redirecting them to the existing discovery surfaces, for example `/drugs` to `/classes` and `/products` or `/companies` to `/search`. A redirect keeps one source of truth and adds no thin pages. This is a one-line `redirects()` entry each in `next.config.ts` and needs approval (it changes routing behaviour).
3. **Fix the breadcrumb structured data** by either omitting the unlinked middle crumb from the JSON-LD or pointing it at the redirect target, after confirming the warning in the Rich Results Test.
4. **Revisit real index pages later** only as filterable, paginated, reviewed-records-only browse pages, designed with the clinical governance owner. `/classes` is the model.

Decision owner: product and clinical governance. Nothing here is implemented.
