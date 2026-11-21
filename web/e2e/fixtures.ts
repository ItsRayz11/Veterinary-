import { test as base, expect, type Page } from "@playwright/test";

/**
 * Failures that are part of normal, correct behaviour. Anything else that fails (any other 4xx/5xx
 * response, an uncaught page error, a console.error) fails the test, so real regressions stay visible.
 *
 * `GET /api/v1/auth/me` answers 403 to signed-out visitors by design (DRF session auth); the app
 * treats it as "not signed in". Browsers log it as a console error, which is why it is named here.
 */
export const EXPECTED_FAILURES: { status: number; path: string; why: string }[] = [
  {
    status: 403,
    path: "/api/v1/auth/me",
    why: "signed-out visitor: the API answers 403 and the app shows Sign in / Register",
  },
];

/**
 * Page errors that are framework behaviour, not application failures. WebKit reports a Next.js
 * link-prefetch (`?_rsc=`) that was cancelled because the page navigated away as an uncaught
 * error ending in "due to access control checks". Matched narrowly (prefetch URL + that message)
 * so any other page error still fails the test.
 */
export const EXPECTED_PAGE_ERRORS: { pattern: RegExp; why: string }[] = [
  {
    pattern: /\?_rsc=[\w-]+ due to access control checks\.?$/,
    why: "WebKit: Next.js prefetch aborted by navigation",
  },
];

export interface Observed {
  expected: string[];
  unexpected: string[];
}

export function classify(status: number, pathname: string) {
  return EXPECTED_FAILURES.some((e) => e.status === status && pathname.startsWith(e.path));
}

type Fixtures = {
  /** Add a pattern for failures this test provokes on purpose (for example a mocked 500). */
  tolerate: (pattern: RegExp) => void;
  observed: Observed;
};

export const test = base.extend<Fixtures>({
  observed: async ({ page }, run) => {
    const observed: Observed = { expected: [], unexpected: [] };
    page.on("response", (r) => {
      if (r.status() < 400) return;
      const u = new URL(r.url());
      const line = `${r.status()} ${u.pathname}`;
      (classify(r.status(), u.pathname) ? observed.expected : observed.unexpected).push(line);
    });
    page.on("pageerror", (e) => {
      const known = EXPECTED_PAGE_ERRORS.some((x) => x.pattern.test(e.message));
      (known ? observed.expected : observed.unexpected).push(`pageerror: ${e.message}`);
    });
    page.on("console", (m) => {
      // "Failed to load resource" lines mirror a response already classified above.
      if (m.type() === "error" && !/Failed to load resource/i.test(m.text())) {
        observed.unexpected.push(`console.error: ${m.text()}`);
      }
    });
    await run(observed);
  },

  // auto: the guard runs for every test, so an unexpected failure can never go unnoticed.
  tolerate: [
    async ({ observed }, run, testInfo) => {
      const patterns: RegExp[] = [];
      await run((p) => patterns.push(p));
      const remaining = observed.unexpected.filter((l) => !patterns.some((p) => p.test(l)));
      if (observed.expected.length) {
        testInfo.annotations.push({
          type: "expected-failure",
          description: [...new Set(observed.expected)].join(", "),
        });
      }
      expect(remaining, "unexpected failed requests or page errors").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };
export type { Page };
