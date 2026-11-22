import { expect, test } from "./fixtures";

// The app has no index page for these sections; bare paths redirect (temporary, 307) to the closest
// real page. Slug routes must keep working (covered by states.spec.ts for the 404 case).
const CASES: [string, string][] = [
  ["/drugs", "/classes"],
  ["/products", "/search"],
  ["/companies", "/search"],
];

for (const [from, to] of CASES) {
  test(`${from} redirects (307) to ${to}`, async ({ request, page }) => {
    const res = await request.get(from, { maxRedirects: 0 });
    expect(res.status()).toBe(307);
    expect(new URL(res.headers()["location"], "http://x").pathname).toBe(to);

    await page.goto(from);
    expect(new URL(page.url()).pathname).toBe(to);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
}

test("slug routes are not swallowed by the redirects", async ({ request }) => {
  const slug = await request.get("/drugs/missing-x", { maxRedirects: 0 });
  expect(slug.status()).toBe(404);
});
