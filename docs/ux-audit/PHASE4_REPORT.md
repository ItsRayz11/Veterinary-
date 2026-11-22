# VetSphere UX Pack, Phase 4 report: review decisions applied

Draft PR #1, not merged, not deployed. No clinical data, calculators, backend, auth, schema or production config changed.

## Done
- **/auth/me 403 (Option A):** unchanged. Tests still fail on any other unexpected error.
- **Redirects:** `/drugs` to `/classes`, `/products` and `/companies` to `/search`, as temporary (307) redirects in `next.config.ts`. Slug routes keep working (404 still real). `e2e/redirects.spec.ts`.
- **Breadcrumb structured data:** checked against Google's documentation (read once via fetch): `item` is required on every crumb except the last. Several pages had middle crumbs without a URL (for example "Calculators", "Companies"). The JSON-LD now leaves those out and renumbers; the visible trail is unchanged. 2 unit tests.
- **Error page wording:** "Nothing you entered has been lost" was not something the page can know; removed. The test now asserts the claim is absent.
- **Error-reporting noise:** cause found earlier (an outage 500 is reported as a bug because Next hides the message in production). Not changed: dropping those reports would also hide real server render bugs, and a digest-only report has no stack. Open decision for the owner.
- **Motion:** the app's motion is small (hover nudges, pulse skeletons, nav bar) and already reduced-motion aware. One real gap fixed: looping skeletons now stop looping under reduced motion (`animation-iteration-count: 1`). Test on all engines. No dependencies added.
- **api-postgres failure:** root cause in `API_POSTGRES_FAILURE.md` (`source_state` is varchar(16), state `linked_unverified` has 17 characters; SQLite does not enforce it). Not caused by this PR. Not fixed: needs a migration, which is not authorised. It may affect production Postgres; I did not check.

## Evidence (GitHub, commit f2ffac8)
- Web E2E success on all four jobs. Unit 206 passed (18 files). Chromium 188 passed. Firefox 179 passed, 2 flaky (the known axe crash retries, passed on retry), 7 skipped. WebKit 178 passed, 10 skipped (7 Chromium-only stack tests, 3 Tab-walk tests).
- `CI` workflow success (the `api-postgres` job is informational and fails as on main; see above).
- Not re-run: the full suite locally, and Lighthouse (no change affects performance paths beyond one CSS line).

## Commits since 334eeee
See `git log 334eeee..f2ffac8` (redirects, breadcrumb/error wording, api-postgres doc, reduced-motion fix) plus this report.

## Still open
Admin screens (needs credentials), analytics (needs privacy review), Firefox axe crash root cause, real WebKit Tab testing, per-page `ApiError` handling, error-reporter outage noise, the `api-postgres` migration, whether to make the redirects permanent. Deployment readiness is not established.
