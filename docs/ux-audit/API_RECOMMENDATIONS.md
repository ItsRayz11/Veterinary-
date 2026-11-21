# API recommendations (not implemented, not approved)

Kept separate from the web work on purpose. Nothing here changes authentication or authorization, and nothing in this phase touched `api/`.

## `GET /api/v1/auth/me` answers 403 to signed-out visitors

**Observed.** Every page load for a signed-out visitor requests `/api/v1/auth/me`; the API answers `403` (`IsAuthenticated` with DRF session auth). Browsers log each one as a console error. Consequences measured in Phase 2:

- Lighthouse best-practices is 96 instead of 100 on every page, and the only failing audit is `errors-in-console`, caused by this one request.
- Any tool that counts browser console errors would count one per signed-out page view. I did not check whether the app's own error reporting (`error-reporter.tsx`) counts it.

**The web app handles it correctly.** `useUser` treats the 403 as "signed out"; the header shows Sign in / Register; no error banner appears (`e2e/auth-console.spec.ts`).

**Options, for the API owner to decide**

| Option | Effect | Cost and risk |
| --- | --- | --- |
| A. Leave as is | No change. The test suite lists this one response as expected (`e2e/fixtures.ts`), so it never hides other failures. | Console noise and the Lighthouse deduction stay. |
| B. Return `200 null` (or `204`) for anonymous callers on `/auth/me` | No error logged. | Changes an API contract the front end, mobile clients or scripts might rely on. The authenticated response and all permissions stay unchanged. Needs a contract note and a test in `api/`. |
| C. Add a separate `GET /auth/session` that always answers 200 with `{user: null | {...}}`, keep `/auth/me` strict | No contract break; the web app switches endpoints. | One new endpoint to secure and document; two ways to ask the same question. |

**Recommendation.** Option C if the noise matters, otherwise A. In both cases keep `/auth/me` strict. No security boundary is involved: the anonymous answer reveals nothing.

## Not part of this recommendation

Nothing about permissions, throttling, CSRF, session handling or the `Cross-Origin-Opener-Policy` header (see the Lighthouse section of the Phase 2 report: that header is a security control and must not be weakened for tooling).
