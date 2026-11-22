# VetSphere UX Pack, Phase 3 report: CI validation, stabilisation, first UX items

Branch `ux/vetsphere-pack-phase1`, draft PR #1 against `main` (not merged, not deployed).
Not touched: clinical data, calculators and their formulas, backend APIs, authentication and authorisation, migrations, production configuration, Vercel settings.

**This phase is not "all UX work done".** It finishes the CI and test stabilisation and delivers the UX items below that had measurable evidence. Section 8 lists what the UX pack asks for that is still open.

## 1. GitHub CI validation (real, remote)

| Pushed commit | Web E2E | Notes |
| --- | --- | --- |
| `291f135` (Phase 2) | success | Chromium 148 passed; Firefox 144 passed + 4 flaky; WebKit 145 passed + 3 skipped |
| `e0de293` | success | Chromium 150 passed; Firefox 147 passed (3 axe retries on `/`); WebKit 146 passed |
| `dfce9e6` (this phase) | success (all 4 jobs) | Chromium **183 passed** (1.2 min, including the 7 slow/failing-backend tests on Linux); Firefox **174 passed** + 2 axe retries on `/` (desktop light and dark) that then passed; WebKit **173 passed**, 10 skipped (7 Chromium-only stack tests + the 3 Tab-walk tests). I read these counts from the job logs after the run; they could not be fetched at first because GitHub became unreachable from my machine for a while. |

- The repository's existing `ci.yml` `web` job was red on `main` at its lint/format/typecheck step. The only problem I found there was a prettier failure in `status-line.tsx` (I did not read the failing log line itself), and the job passes on this branch after that whitespace-only fix. `api` passes. `api-postgres` fails exactly as it does on `main` (informational, `continue-on-error`); I did not investigate it.
- Linux fonts did **not** change the responsive results: every width/route test passed on GitHub's Ubuntu runners for all three engines (the main residual risk I had flagged).
- **Vercel preview deployments were created** for both projects on the first PR push (statuses "Deployment has completed"), as predicted from the project settings, not prevented. I did not re-check later pushes. Every environment variable on both Vercel projects is scoped to `production` only, so previews carry no secrets and no database access; production deploys only from `main`. Values were never read or printed.

## 2. Stabilisation work

| Problem | Finding | Outcome |
| --- | --- | --- |
| Service-worker slow-network unit test failed 1 in 3 solo runs under load | It asserted real elapsed time and slept 300 ms | Rewritten with a controlled clock (`setTimeout`/`clearTimeout`/`Date` only; faking `setImmediate` hangs `Response.text()`). 8 of 8 runs pass. Mutation checks: serving the offline page on timeout fails with `expected 'cached /offline' to be 'old copy'`; blocking the late refresh fails with `expected 'old copy' to be 'new copy'`. Assertions are not weakened. |
| Firefox `Page crashed` during axe | Reproduced about 30% locally and about 4 of 32 first attempts on GitHub; ten variants did not remove it | **Not root-caused.** Mitigated with 3 visible retries on axe tests only. Full evidence: `FIREFOX_AXE_CRASH.md`. |
| WebKit never Tabs to links | Confirmed (Tab only reaches inputs; Alt+Tab does not change it) | 3 Tab-walk tests stay skipped on WebKit. New tests derive the focus order from the DOM (no positive `tabindex`, skip link first, header then main then footer) and activate the skip link and a nav link with Enter on **all** engines. **Real Tab traversal of links is still untested on WebKit.** |
| Spurious `500 /api/v1/auth/me` (2 in 471 tests) | Keep-alive race between the app's proxy and my mock API, not the app | Mock now closes connections. |
| Tests that typed before React hydrated (WebKit) | `fill()` ran before hydration, so values were dropped; a hostile-input test could pass vacuously | `waitForHydration` helper in the calculator tests. |

## 3. Navigation feedback (new, measured)

**Problem proven.** On a mock API that takes 2 s, tapping a tab left the old page on screen with no indicator for about 1.8 s; the URL did not change until the data arrived.

**What I did not do, and why.** A `loading.tsx` is the obvious fix, but Next.js documents that streaming fixes the HTTP status early. That would turn this app's real `404` for unknown drug/product/company/species slugs into `200` soft-404s and outage `500`s into `200`. A test now guards the 404 behaviour (below).

**What I did.** `NavigationProgress` (client component): listens for internal link clicks (`startsNavigation`, a pure function with 5 unit tests: modified clicks, new tabs, other origins, same page), shows a 3 px bar that fades in after 120 ms (fast navigations never flash it) and a polite "Loading page" status after 400 ms, until the URL changes. It gives up after 15 s. Reduced motion: a static full-width bar. It touches no routing or server behaviour.

**Measured** (fresh cache and a fresh port pair, 2 s API, tap at t=0):

| Time after tap | Before | After |
| --- | --- | --- |
| 150 ms | old page, no indicator | old page, progress bar present |
| 500 ms to 2.5 s | old page, no indicator | old page, bar + "Loading page" announced |
| about 3.5 s | new page | new page, indicators gone |

An early "after" run looked instant (150 ms) because the server's own 60 s data cache had been filled by my earlier measurement on the same API address; I caught that, discarded it, and repeated on a fresh port pair. Practical note: pages served from that cache are fast; the bar matters for cold or uncached loads (first visits, search, detail pages).

## 4. Error state (new, found by observation)

**Problem proven.** With the data service down, every data page answers HTTP `500` and shows the generic "This page could not be loaded". `error.tsx` was written to show a specific "data service is currently unreachable" message, but **Next.js hides server error messages in production**, so that branch can never run there. The same check also gates `reportError`, so outages are reported as bugs.

**Fix.** The generic text now says the likely cause, that nothing is lost, and offers a 44 px "Try again" and "Go to the home page". The status stays 5xx (an outage is not disguised as success). Per-page handling of `ApiError` (as `/search` already does) would be better but touches about 20 pages; not done. The error-reporting noise is **not** fixed.

## 5. Review-status badge hardening (clinical-safety display)

`StatusLine` picked the badge from `status.code` only. A contradictory record (`code: "verified"` or `"expert_reviewed"` with `is_unverified_import: true`) rendered **"Verified"** on an unreviewed import. 15 new tests cover every code, the fallback for unknown codes, development data, and the contradictory combinations; **2 failed before the fix**. The fix (9 lines) only ever downgrades a reviewed badge to "Imported, not reviewed" when the record is flagged as an unverified import. No data, status, API or other combination changes. Whether the API can actually produce such a contradiction is unknown to me; this is defence in depth.

## 6. Calculators (inspected, no defect found)

All eight calculators: numeric inputs have accessible names, results sit in one polite live region with units, axe is clean (phone, light), and blank, zero, negative, text, `1e309`, 20-digit and tiny values never show `NaN`, `Infinity`, `undefined` or `null`, or throw. The dilution calculator's 10/2/100 gives 20.00 mL stock and 80.00 mL diluent (the same arithmetic the repo's `scripts/browser-check.mjs` already asserts), and an impossible target shows an alert that clears when fixed. **No clinical value was asserted and no formula was changed.** 26 tests per engine, all three engines pass (one WebKit axe retry).

## 7. Looked at and left alone (adequate as built)

- Dialogs use the native `<dialog>` with `showModal()`, so focus trap, Escape and focus return come from the browser.
- Status badges carry text labels, not colour alone.
- Unknown slugs return a real 404 (now covered by tests).

## 8. Not done (still open from the UX pack)

Not started, with the reason: filter chips and a mobile drawer (the app has no drawer; no filter control was found to improve), reference-card source labels beyond the existing status text, admin dashboard polish (needs an authenticated admin; not testable without credentials, which I did not use), related-content discovery, motion tokens and wider motion polish, privacy-reviewed analytics (needs a privacy review you have not authorised), per-page `ApiError` handling, the `error-reporter` noise, the `/blog` mock shape (my mock returns `[]` where the real API returns a paginated object, so `/blog` 500s in tests; not an app bug), and Firefox/WebKit root causes. The three route-index decisions (`ROUTE_INVENTORY.md`) and the `/auth/me` API choice (`API_RECOMMENDATIONS.md`) still need your decision.

## 9. Numbers (local, one Windows machine; GitHub results are in section 1)

- Unit: **17 files, 204 tests passed** (184 earlier + 5 navigation + 15 status-line).
- Lint 0 errors (1 pre-existing warning), typecheck clean, build compiled.
- Browser: **549 tests listed** (183 per engine; the 7 stack tests run on Chromium only). Last full local run, before the calculator and status work: 445 passed, 6 flaky, 3 failed, 17 skipped in 39.6 minutes (the machine had about 2 GB free RAM; Firefox was slow). Of those 3 failures: 2 Firefox context-teardown timeouts (a Firefox harness problem, probably memory pressure; not proven) and 1 spurious `500 /api/v1/auth/me` from the mock keep-alive race (the Chromium flaky one had the same cause), since fixed. The calculator spec afterwards: 77 passed, 1 flaky, 0 failed on all three engines.
- Not re-run end to end locally after the final test edits: the full 549-test suite. GitHub's run on `dfce9e6` is the first complete run of everything together; its counts are in section 1.

### Performance check of the navigation component (local Lighthouse, noisy)

Same method as Phase 2 (local production build, mock API, Chrome 157, COOP header stripped by the tooling proxy, 2 runs per page and form factor, machine with about 2 GB free RAM). The build used was made before the status-badge fix, which does not touch `/` or `/search`.

| Page, form factor | LCP before (Phase 2) | LCP now | TBT now (2 runs) |
| --- | --- | --- | --- |
| `/` mobile | 1221, 1221 ms | 1159, 1251 ms | 166, 616 ms |
| `/search?q=amox` mobile | 905, 864 ms | 794, 987 ms | 660, 139 ms |
| `/` desktop | 305, 300 ms | 325, 333 ms | 1511, 24 ms |
| `/search?q=amox` desktop | 481, 479 ms | 494, 492 ms | 6, 10 ms |

CLS stays 0; accessibility stays 100, best-practices 96, SEO 100 (`/search` 63, deliberately `noindex`). Desktop LCP is consistently about 13 to 33 ms higher; mobile LCP is within the spread. Total blocking time varies from 6 to 1511 ms between runs of the same page, so it says nothing about this change. **Conclusion: no regression shown, but a cost of tens of milliseconds cannot be ruled out on this machine.** A quieter machine or CI-based Lighthouse would settle it; I did not do that.

## 10. Rollback

`git revert` the Phase 3 commits (`dd953ca`, `8ef9b9b`, `dfce9e6` and this docs commit). No data, schema, configuration or infrastructure changes were made.
