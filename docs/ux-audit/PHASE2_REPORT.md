# VetSphere UX Pack, Phase 2 report: cross-browser QA and CI

Branch `ux/vetsphere-pack-phase1`. Local commits only: nothing pushed, merged or deployed.
Phase 1 commits `0a0f5ad`, `4f1b223`, `7808856` are unchanged.
Not touched: clinical data, calculators, medication logic, backend APIs, authentication and authorization, migrations, production configuration.

## 0. Local results versus GitHub Actions

**Everything below was run locally on one Windows machine. The GitHub Actions workflow has been written and parsed as YAML, but it has not run on GitHub.** Whether it passes there is unproven: Linux fonts, runner speed and the Playwright system dependencies can all differ.

## 1. Playwright suite

`web/e2e/`, run with `npm run build` then `npm run test:e2e` (`npx playwright test --project=chromium|firefox|webkit`).

| File | Covers | Tests per engine |
| --- | --- | --- |
| `responsive.spec.ts` | 12 widths (the 11 you listed plus 430) x 7 routes: no horizontal overflow, exactly one nav, footer follows the layout, nothing hidden behind the tab bar, tabs and auth links at least 44x44, no truncated tab labels | 84 |
| `a11y.spec.ts` | axe-core (WCAG 2.0/2.1/2.2 A and AA plus best-practice) on 8 routes x phone/desktop x light/dark, plus the search suggestion states | 33 |
| `search.spec.ts` | URL to input sync (encoded, UTF-8, special characters, `<script>`), empty and 1-character queries, submit/back/forward, slow/stale/failed responses, rapid typing, clear, arrow keys and Escape, no-match ARIA | 17 |
| `navigation.spec.ts` | Tab order and focus rings, skip link, hidden nav not reachable, reduced motion, signed-out and mocked signed-in header at 390/768/1280 | 11 |
| `auth-console.spec.ts` | the expected `/auth/me` 403 versus genuine failures | 3 |
| **Total** | | **148** (x3 engines = **444**) |

**Isolation.** The suite serves a production build with `API_URL` pointed at `e2e/mock-api.mjs`, a 35-line dependency-free server with synthetic fixtures (names start with `FIXTURE-`). No Django, no database, no live data, no credentials, no administrative account. The signed-in state is a mocked response with a synthetic user. Browser-side calls are intercepted per test with `page.route()`.

**Design choices worth knowing**
- **One test per width and route** (not a loop). A failure names the exact page, and a slow engine can never hit a timeout across a long loop (the first design did, on Firefox and WebKit).
- **Layout invariants are polled** (`expect.poll`) so a layout that is still settling passes, but a persistent defect fails.
- **Service workers are blocked** (`serviceWorkers: "block"`). Playwright's `page.route()` cannot see requests a service worker handles; in WebKit that made mocked search responses silently bypass the mock. The worker's logic is covered by `src/lib/sw.test.ts` (20 tests).
- **Traces on first retry only.** Recording response bodies on every first run made Firefox teardown time out here.
- **Mutation check.** With the original `sm:` breakpoints temporarily restored and rebuilt, all 21 tests at 640, 768 and 820px failed (message: `horizontal overflow 164px, top nav visible=true, bottom tab bar visible=false`) while the 1024px tests passed. The fix was then restored and rebuilt; 35 responsive tests passed again.

## 2. GitHub Actions workflow (`.github/workflows/web-e2e.yml`)

- **Trigger:** `pull_request` to `main` (only when `web/**` or the workflow changes). No `pull_request_target`.
- **Permissions:** `contents: read`. No secrets referenced. `persist-credentials: false` on checkout.
- **Jobs:** `quality` (`npm ci`, lint, prettier check, typecheck, `npm test`), then `e2e` as a matrix over `chromium`, `firefox`, `webkit` (`needs: quality`, `fail-fast: false`): `npm ci`, `npm run build`, `npx playwright install --with-deps <browser>`, `npx playwright test --project=<browser>`.
- **Artifacts (always, 14 days):** `playwright-report/` and `test-results/` (screenshots on failure, traces on retry).
- **CI settings in the Playwright config:** 2 workers, 1 retry, `forbidOnly`.
- **Package manager:** the repo's npm and `package-lock.json`; `npm ci --dry-run` succeeds.
- **Overlap:** the existing `ci.yml` `web` job (push and PR) also runs lint, format, typecheck, test and build. The new `quality` job repeats those; I kept it so this workflow is a complete gate by itself. Merging the two is a cleanup for you to choose.
- **Not done:** making this check *required* on `main` is a GitHub branch-protection setting, which I did not touch. Note: the workflow has a `paths` filter, so on a PR that touches nothing under `web/` it does not run; if it is later made a required check, GitHub would wait for it forever on such PRs, so either drop the filter or add a no-op fallback job at that point.

## 3. Browser compatibility (local run, 444 tests, 9.1 minutes)

Playwright 1.65.1 builds: Chromium 159.0.8154.6 (Chrome for Testing), Firefox 159.0, WebKit 27.2. WebKit here is Playwright's engine build on Windows; **it is not Safari and not iOS**.

| Engine | Passed | Failed | Skipped |
| --- | --- | --- | --- |
| Chromium | 148 | 0 | 0 |
| Firefox | 146 | 2 | 0 |
| WebKit | 145 | 0 | 3 |

**The 2 Firefox failures** are `frame.evaluate: Page crashed` while axe scanned `/` at desktop width (light and dark). Re-run alone three times, it crashed once and passed 8/8 twice. It is an intermittent Firefox page crash, not an axe rule result, and I have not identified its cause. I have not classified it as an accessibility defect or an application bug. The CI retry will show whether it recurs on GitHub's runners.

**The 3 WebKit skips** are Tab-walk tests: WebKit never Tabs to links (it tabs only to form controls), a Safari-style default and not an app bug. The engine-neutral test "every interactive control shows a focus ring" runs on all three engines and passes. **Tab-key navigation of links is therefore not tested on WebKit.**

**Issues found and fixed while stabilising the suite (all test-side, none in the app):** an ambiguous "Sign in" locator on `/study`; per-test timeouts from looping over routes on slower engines; service-worker interception in WebKit; WebKit's aborted-prefetch page error (see below). The one allow-listed page error is WebKit reporting a cancelled Next.js link prefetch (`?_rsc=...` ending "due to access control checks"), matched by that exact pattern only.

**Not tested:** real Safari or iOS, Chrome on Android, real touch hardware, screen readers, authenticated admin screens, Linux fonts (the CI runner will be the first Linux run).

## 4. Test counts

- Unit (vitest): **184 passed, 15 files** (176 original + 8 from Phase 1). Unchanged by Phase 2 apart from one updated assertion (auth links now `min-h-11 min-w-11`).
- Browser (Playwright): **444** (148 x 3 engines): 439 passed, 2 failed (Firefox crash above), 3 skipped (WebKit Tab).
- Lint: 0 errors, 1 pre-existing warning. Typecheck: exit 0. Build: compiled. Prettier: clean (with line endings normalised; this Windows checkout converts to CRLF).
- Known flaky unit test: `src/lib/sw.test.ts` "serves the saved copy when the network is slow" failed once in 3 solo runs under CPU load and passes in the full suite. It is untouched by this work and pre-existing.

## 5. Responsive results, including 430px

All 12 widths x 7 routes (320, 375, 390, **430**, 640, 768, 820, 910, 1024, 1280, 1440, 1920) pass on all three engines: no horizontal overflow, exactly one nav (bottom bar below 1024px, top nav and footer from 1024px), nothing hidden behind the tab bar, no truncated tab labels, tabs and auth links at least 44x44.

## 6. Mobile navigation (commit `4ff5d80`)

- **Cause (measured, Chrome):** at 390px each of the 6 tabs was 65px wide; "Scholarships" at 11px needs 67px, so it was ellipsised. Calculators and Universities came close.
- **Fix:** tabs size to content (`flex-auto`) with a 44px minimum (`min-w-11`), no extra horizontal padding, and 10.5px labels with slightly tight tracking. Summed label width is about 252px, so even 320px has about 20px to spare. Labels stay full words; accessible names are unchanged; no new elements, no animation.
- **Touch targets:** tabs, "Sign in", "Register", account and "Sign out" links and the search clear button are now at least 44x44 (were 40px).

## 7. Accessibility

axe-core with WCAG 2.0, 2.1 and 2.2 A/AA plus best-practice rules, 8 routes in 4 modes (phone and desktop, light and dark) plus the open-suggestions and no-match search states: **no violations on Chromium or WebKit**, and none on Firefox apart from the 2 crashes above (no rule result was produced for those two attempts; desktop light passed on 2 of 3 solo re-runs, and desktop dark was not re-run separately). Automated checks find only part of what a screen reader user would meet; none of this replaces manual testing.

## 8. Lighthouse investigation

**Cause of `NO_NAVSTART`: the app's `Cross-Origin-Opener-Policy: same-origin` response header.** Evidence:

| Experiment | Result |
| --- | --- |
| Lighthouse 13.6.0 + Chrome 157 on a trivial static page | works (so tool and browser are compatible) |
| Our page with the service worker blocked (`--blocked-url-patterns`) | still `NO_NAVSTART`: service worker ruled out |
| Our page through a tooling-only proxy dropping only the CSP | still `NO_NAVSTART`: CSP ruled out |
| Our page through a tooling-only proxy dropping only COOP | **works** (performance 100, LCP 1076 ms) |

COOP `same-origin` swaps the browsing context on navigation, which is a known way for Lighthouse to lose the `navigationStart` trace event. **The header is a security control; I did not change it.** The proxy (`docs/ux-audit/qa-scripts/lighthouse/coop-proxy.mjs`) lives only in the tooling folder and runs only against a local build.

**Measurements** (local production build, mock API, headless Chrome 157 via the proxy, Lighthouse default simulated throttling, 2 runs each, otherwise idle machine). These are diagnostics for this machine, **not production field data, and there is no before/after baseline** (the Phase 1 original code was not measured):

| Page | Form factor | Perf | A11y | Best practices | SEO | FCP / LCP (ms) | TBT (ms) | CLS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/` | mobile | 100, 100 | 100 | 96 | 100 | 1221 / 1221 | 56, 64 | 0 |
| `/search?q=amox` | mobile | 99, 100 | 100 | 96 | 63 | 905, 864 / same | 104, 61 | 0 |
| `/` | desktop | 100, 100 | 100 | 96 | 100 | 305, 300 / same | 0 | 0 |
| `/search?q=amox` | desktop | 100, 100 | 100 | 96 | 63 | 481, 479 / same | 0 | 0 |

- **Best practices 96:** the only failing audit is `errors-in-console`, which is the signed-out `403 /auth/me` (see `API_RECOMMENDATIONS.md`).
- **`/search` SEO 63:** the `is-crawlable` audit fails because the search page is deliberately `noindex`.
- Informational insights only: forced reflow, network dependency tree, and bfcache blocked by `Cache-Control: no-store` on dynamic pages (Lighthouse marks it not actionable).
- To repeat: `docs/ux-audit/qa-scripts/lighthouse/` (`coop-proxy.mjs`, `lh-all.sh`, `sum2.mjs`). Raw JSON reports were not committed.

## 9. Auth console handling

`GET /api/v1/auth/me` answering 403 to signed-out visitors is intentional and unchanged. The front end treats it as "not signed in" (verified: Sign in and Register shown, no error banner, no other failures). The test fixture lists **only that one status and path** as expected; any other 4xx/5xx, uncaught page error or `console.error` fails the test, and two tests prove it (a 500 on search, and a 500 on `/auth/me` itself, are both reported as unexpected). Each test records the tolerated 403 as an annotation so it stays visible in the report. Possible API changes are written up separately in `API_RECOMMENDATIONS.md`; none is implemented or approved.

## 10. Missing index pages

See `ROUTE_INVENTORY.md`. Short version: `/drugs`, `/products`, `/companies` are intentionally absent (product spec: slug pages only, "no thin programmatic pages"); no link points at them. Recommendation: do not create flat index pages; if the user problem matters, redirect the bare paths to existing discovery pages (`/classes`, `/search`) after approval; separately, confirm and fix the breadcrumb structured-data entry that has no URL. Nothing was created or changed.

## 11. Commits

| Hash | Subject |
| --- | --- |
| `4ff5d80` | fix(web): bottom tab bar labels no longer truncate; 44px touch targets |
| `4043804` | style(web): prettier formatting of status-line.tsx (whitespace only; `git diff -w` empty) |
| `c99e827` | test(web): Playwright setup, isolated mock API, failure-classifying fixture |
| `c48d3b3` | test(web): browser regression specs |
| `1e9d0ff` | ci: Web E2E workflow |
| (this docs commit) | docs: Phase 2 report, route inventory, API recommendations, Lighthouse tooling |

`01_VetSphere/` and `.scratch_baseline.txt` are not committed. The `status-line.tsx` change is whitespace-only; I flag it because the file displays review status and I did not want it to pass unnoticed.

## 12. Remaining risks and deployment readiness

- **The CI workflow has not run on GitHub.** Treat the first PR run as the real test. Expect possible first-run issues (Linux fonts changing label widths, system dependencies, slower runners).
- **Firefox intermittent page crash** during axe on `/` at desktop width is unexplained.
- **WebKit Tab-to-link is untested**, and Playwright's WebKit is not Safari.
- **Pre-existing:** flaky `sw.test.ts` timing test; console 403 noise; 404 on bare index paths.
- **No before/after performance baseline** exists; Lighthouse numbers are one machine, mock data, one header stripped for measurement.
- **Not production-ready by this evidence alone.** This phase adds a regression gate and small front-end fixes. It does not establish production readiness; deployment, merging and pushing remain unapproved and untouched. Rollback: `git revert` the commits above (no data, schema or configuration changes were made).
