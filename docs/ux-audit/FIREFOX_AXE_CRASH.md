# Firefox page crash during axe scans (investigation record)

**Status: reproduced, not root-caused. Mitigated in the test suite; no application change.**

## Symptom

`frame.evaluate: Page crashed` inside `AxeBuilder.analyze()` (`runPartialRecursive`) in Playwright's Firefox (159.0). The browser's own `crash` event fires, so the content process really dies. Only the axe tests are affected; every other Firefox test, including ones that load the same pages, passes.

| Where | Rate |
| --- | --- |
| Local (Windows, 4 CPUs, 15.8 GB RAM, about 2 GB free at the time) | about 30% of attempts on `/` (9 of 30 in the baseline run) |
| GitHub Actions (ubuntu-latest), first Playwright run | 4 of 32 Firefox axe tests failed on attempt 1 and passed on the retry: `/` in 3 modes, `/study` in 1 |

Chromium and WebKit never crashed (axe tests passed on every run).

## Experiments (30 attempts each unless noted, `/`, phone and desktop, no retries)

| Variant | Crashes | Conclusion |
| --- | --- | --- |
| Baseline | 9 / 30 | reproducible |
| `color-contrast` rule disabled | 9 / 30 | not the rule engine's heaviest rule |
| Wait for network idle first | 10 / 30 | not about the page still loading |
| Wait a flat 2 s first | 9 / 30 | not timing |
| Scroll-driven `.reveal` animation disabled | 10 / 30 | not scroll-driven animation |
| `backdrop-filter` disabled | 10 / 30 | not the glass blur |
| axe legacy mode (skips the partial-results path) | 10 / 30 | not `runPartialRecursive` |
| One worker instead of two | 7 / 15 so far (run stopped) | not parallelism or inter-worker memory pressure |
| All inline SVG hidden, whole page | 8 / 30 | not the icons alone |
| Scan only `header` | 0 / 20 | header is not a trigger |
| Scan only section 1 (hero) | 0 / 20 | not a trigger |
| Scan only section 2 | 2 / 20 | weak |
| Scan only section 3 ("Study and careers", 4 `FeatureCard`s) | 7 / 20 | strongest single region |
| Section 3 with: gradient removed / transitions and animations off / line-clamp off / box-shadow off / icons hidden | 4 / 10\*, 6 / 20, 8 / 20, 4 / 20, 2 / 20 | none removes it; hiding icons lowered it most but not to zero |

\* ten of the 20 attempts in that variant failed on connection errors caused by an overlapping run of mine and were discarded; the 10 valid attempts are shown.
The footer-only variant was invalid for the same reason and was not repeated.

## What this does and does not say

- It is **not** a timing, concurrency, single-rule, single-CSS-feature or single-axe-code-path problem, as far as the variants above can show.
- It points at a Firefox content-process crash that is triggered by axe-core's heavy DOM and style queries over pages that contain these card layouts. The cause inside Firefox is **unverified**.
- **No end-user impact is shown.** Normal Firefox page loads of the same pages passed in every other test (12 widths on `/`, keyboard, search, reduced motion). The crash needs the analysis load, which real visitors never create. This is a statement about the tests I ran, not proof that no user can ever hit a crash.

## Mitigation (test-side only)

`e2e/a11y.spec.ts` allows up to 3 retries for the axe tests. Accessibility violations are deterministic and fail every attempt, so a retry cannot hide one. Each retry is recorded as an `axe-retry` annotation and the report lists the test as flaky, so the crash rate stays visible.

## If you want to dig further

- Try a newer Playwright Firefox build (this suite pins 1.65.1, Firefox 159).
- Capture a Firefox crash report or minidump from a failing run and file it with Mozilla, attaching the page and the axe version (`@axe-core/playwright` 4.14). I did not try this.
- Re-run the section bisect with finer granularity inside the "Study and careers" section (single card, single child).
