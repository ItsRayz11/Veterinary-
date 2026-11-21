import type { Page, Route } from "@playwright/test";

/** The 11 target widths plus 430, which the Phase 1 after-fix run did not cover. */
export const WIDTHS = [320, 375, 390, 430, 640, 768, 820, 910, 1024, 1280, 1440, 1920] as const;

/** Where the layout switches from the bottom tab bar to the top nav (Tailwind `lg`). */
export const DESKTOP_NAV_MIN_WIDTH = 1024;

/** Routes that render without any API data, so they are stable under the mock API. */
export const ROUTES = ["/", "/search", "/calculators", "/study", "/login", "/register", "/offline"];

/** SYNTHETIC user for the mocked signed-in state. Never a real account. */
export const MOCK_USER = {
  id: 1,
  username: "test-user",
  email: "test-user@example.test",
  role: "viewer",
};

export const emptySearch = { generics: [], products: [], companies: [], did_you_mean: [] };

export const fixtureSearch = (name: string) => ({
  ...emptySearch,
  generics: [{ name: `FIXTURE-${name}`, slug: `fixture-${name}` }],
});

export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

/** Intercepts the browser's suggestion requests (the app's own proxy path). */
export async function mockSearch(
  page: Page,
  handler: (route: Route, q: string) => Promise<unknown> | unknown,
) {
  await page.route("**/api/v1/search**", (route) => {
    const q = new URL(route.request().url()).searchParams.get("q") ?? "";
    return handler(route, q);
  });
}

/** Pretends the visitor is signed in. The API is never contacted for this. */
export async function mockSignedIn(page: Page) {
  await page.route("**/api/v1/auth/me**", (route) => json(route, MOCK_USER));
}

/** The header's Sign in link. Some pages (for example /study) have their own in-page Sign in link. */
export const headerSignIn = (page: Page) =>
  page.getByRole("banner").getByRole("link", { name: "Sign in" });

export const searchInput = (page: Page) => page.locator("#global-search");

/** Replaces whatever is in the search box (more reliable than a triple click across engines). */
export async function setQuery(page: Page, text: string) {
  const input = searchInput(page);
  await input.click();
  await input.fill("");
  await input.pressSequentially(text);
}
