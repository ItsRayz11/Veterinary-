import { expect, test } from "./fixtures";
import { headerSignIn, json, mockSearch, setQuery } from "./helpers";

/**
 * `GET /api/v1/auth/me` answers 403 to signed-out visitors by design. These tests pin down that
 * (a) the app handles it as "not signed in" and (b) only that one failure is treated as expected,
 * so a genuine failure still fails a test instead of hiding behind the known noise.
 */
test.describe("auth console behaviour", () => {
  test("signed-out: the single 403 is expected, handled, and the UI is correct", async ({
    page,
    observed,
  }) => {
    await page.goto("/");
    await expect(headerSignIn(page)).toBeVisible();
    await expect(page.getByRole("link", { name: "Register" })).toBeVisible();
    // No visible error banner or crash screen from the expected 403 (Next keeps an empty
    // route-announcer alert in the DOM, so only alerts that actually say something count).
    await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveCount(0);

    expect(observed.expected.length, "the signed-out check ran").toBeGreaterThanOrEqual(1);
    expect(new Set(observed.expected)).toEqual(new Set(["403 /api/v1/auth/me"]));
    expect(observed.unexpected).toEqual([]);
  });

  test("an unexpected failure is NOT hidden by the allow-list", async ({
    page,
    observed,
    tolerate,
  }) => {
    tolerate(/500 \/api\/v1\/search/); // this test provokes it on purpose and asserts it is seen
    await mockSearch(page, (route) => route.fulfill({ status: 500, body: "boom" }));
    await page.goto("/search");
    await setQuery(page, "anything");
    await expect.poll(() => observed.unexpected.join()).toContain("500 /api/v1/search");
  });

  test("the same path with another status is still unexpected", async ({
    page,
    observed,
    tolerate,
  }) => {
    tolerate(/500 \/api\/v1\/auth\/me/);
    await page.route("**/api/v1/auth/me**", (route) => json(route, { detail: "boom" }, 500));
    await page.goto("/");
    await expect.poll(() => observed.unexpected.join()).toContain("500 /api/v1/auth/me");
    // The header still falls back to the signed-out controls instead of breaking.
    await expect(headerSignIn(page)).toBeVisible();
  });
});
