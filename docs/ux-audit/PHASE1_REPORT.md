# VetSphere UX Pack, Phase 1 report

Branch `ux/vetsphere-pack-phase1`. Local commits only: nothing pushed, merged or deployed.
Scope: the web app in `web/` (this repo is branded VetRef; the official origin constant is `vetsphere.xyz`).
Clinical data, calculators, medication logic, the API and production configuration were not touched.

## 1. Check results (all run to completion on the final tree)

| Check | Result |
| --- | --- |
| `npm run lint` | 0 errors, 1 warning (pre-existing, `scripts/a11y-check.mjs`) |
| `npm run typecheck` | exit 0 |
| `npm run build` | compiled successfully |
| `npm test` (vitest) | 15 files, 184 tests passed (176 existing + 8 new) |
| Prettier on touched files | clean. 4 untouched files already fail `prettier --check` (`companies/[slug]`, `drugs/[slug]`, `status-line`, `status-badge`) |

## 2. Defects fixed (each reproduced before it was fixed)

1. **Horizontal overflow between 640 and about 900px.** The 7-item top nav is shown from 640px but needs about 910px. Fix: nav, footer and bottom tab bar all switch at `lg` (1024px) instead of `sm`.
2. **Sign in / Register / Sign out were 20px tall.** Now 40px.
3. **`/search?q=...` rendered an empty input.** The box now shows the URL query, has a clear button (40px target, returns focus to the input) and an accessible "Searching..." status. The box is keyed on the URL query so back/forward keep input and URL in sync.
4. **Found by axe during verification (critical, `aria-required-children`):** the suggestion listbox could contain no options. Two causes: the URL-seeded box auto-fetched suggestions on load (my change), and a no-match result rendered an empty `role=listbox` (latent in the original code). Suggestions now fetch only after the user types, and the no-match message is a `role=status`.

Search results logic and the API contract are unchanged.

## 3. Responsive audit (identical script before and after, 9 routes per width)

Measured with `document.scrollWidth - clientWidth`, not screenshots. Raw output: `width-audit-before.txt`, `width-audit-after.txt`.

| Width | Overflow before | Overflow after | Nav (after) | Auth link height before / after |
| --- | --- | --- | --- | --- |
| 320, 375, 390 | none | none | bottom | 20 / 40 px |
| 640 | **+268 px** | none | bottom | 20 / 40 |
| 768 | **+140 px** | none | bottom | 20 / 40 |
| 820 | **+88 px** | none | bottom | 20 / 40 |
| 910 | none | none | bottom | 20 / 40 |
| 1024, 1280, 1440, 1920 | none | none | top + footer | 20 / 40 |

After the fix, at every width: exactly one of the two navs is visible, the bottom bar never covers the last content, the hidden nav is `display:none`.
430px is not in the final 11-width run. It was measured once, on the original build only (no overflow); it was not re-measured after the fix.

Screenshots: `screens/before-768-header.png`, `screens/after-768-header.png`, `screens/before-search-390.png`, `screens/after-search-390.png`.

## 4. Search verification (39 browser checks, all pass on the fix)

Run against `/api/v1/search` with synthetic fixtures (not real drug data). On the original build the same suite fails: query lost on load, no clear button, no loading status, back/forward leaves a stale input.
Covered: normal, space, `+`, UTF-8, `&=+/?#"<>'` and a `<script>` payload (inert); empty and `q=`; 1-character query; submit then back then forward; a slow response not overwriting a newer one; rapid typing; failed request then recovery; clear while a request is in flight; Escape and arrow-key behaviour; no-match ARIA; no fetch on load.

## 5. Other verification

- **Keyboard:** first 10 Tab stops show a focus outline and are on-screen at 1280 and 390.
- **Reduced motion:** transitions about 0 and no animation over 50ms with `prefers-reduced-motion: reduce`.
- **Logged in / out:** logged-out verified against the real API. Logged-in verified with a **mocked** `/auth/me` response (synthetic user); no real account was used.
- **axe-core** (existing `web/scripts/a11y-check.mjs`, phone and desktop, light and dark): 16 pages clean, including `/search?q=amox`. `/admin-panel` and `/account` were checked in their signed-out state only; authenticated admin screens were not tested.

## 6. Console errors, root causes

| Response | Cause | Verdict |
| --- | --- | --- |
| `403 /api/v1/auth/me` (once per page for signed-out visitors) | `me` requires `IsAuthenticated`; DRF session auth answers anonymous callers with 403 | By design, handled in `useUser`. It shows as a console error on every page. Removing it needs an API change (for example 200 with null), which was not authorised. Not silenced. |
| `404 /drugs`, `/companies`, `/products` | Only `[slug]` routes exist; there is no index page. No link in the app points at these paths (the drug breadcrumb renders "Drugs" as plain text). | My own probe, not an application defect. Phase 2 candidate: index pages or redirects. |

## 7. Performance

- **Lighthouse: unavailable.** Lighthouse 13.6.0 with Chrome 157 failed `NO_NAVSTART` (trace recording) in three configurations (CLI, CLI with other flags, via puppeteer). No scores are reported and none are invented.
- No before/after Core Web Vitals were collected. The change set is CSS class swaps plus a small amount of client code in the search box (bundle size not measured); no performance claim is made.

## 8. Domain and deployment mapping

Evidence that this code serves `vetsphere.xyz`: `docs/DEPLOYMENT.md` (Vercel web project, root `web`, CORS/CSRF set to that origin); `web/src/lib/site.ts`; DNS resolves; the live response has `Server: Vercel`, `X-Powered-By: Next.js` and a CSP whose `worker-src`, `manifest-src`, `frame-ancestors` and `object-src` directives match `web/src/lib/security-headers.ts`.
**Limit:** this is strong circumstantial evidence, not proof that the live site runs this exact commit. Nothing was changed in domain configuration.

## 9. Not tested (stated plainly)

- **Firefox and WebKit: untested.** Everything ran in Chrome 157 (installed Chrome driven by puppeteer-core, since the Claude-in-Chrome extension was not connected).
- No real touch hardware or screen reader.
- No authenticated admin flows, no production or staging environment.
- No Lighthouse or Core Web Vitals.
- The local API ran against a throwaway migrated SQLite database with no content; result lists were exercised with synthetic fixtures only.

## 10. Remaining issues

- **P1:** none confirmed open in the areas tested.
- **P2:** `403 /auth/me` console noise (needs API decision). Mobile bottom-bar labels truncate at 390px ("Scholarsh..."). `/drugs`, `/companies`, `/products` index 404s. The a11y script's default page list includes `/drugs`, which 404s.
- **Environment notes:** `next dev` stalled on this slow disk (use a production build); the repo's local `api/db.sqlite3` is behind on migrations (`pharma_product.listing_kind` missing), which is why a scratch DB was used.

## 11. Rollback

`git revert` the two Phase 1 commits (or `git reset --hard ddff2c3` on this branch). No data, schema or configuration changes were made.

## 12. Phase 2 recommendations

1. Playwright suite in CI (`ux-pack/qa-starter` is the starting point) running the scripts in `qa-scripts/`, with Firefox and WebKit.
2. Decide on the `/auth/me` 403 (API change) so consoles are clean.
3. Mobile bottom bar: 6 labels at 390px truncate; consider "More" or shorter labels.
4. Index pages or redirects for `/drugs`, `/companies`, `/products`.
5. Source and review-status labelling on reference cards, per the pack's backlog, using existing data only.
6. Lighthouse CI once a compatible Chrome and Lighthouse pair is found.
