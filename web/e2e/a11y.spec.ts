import {
  emptySearch,
  fixtureSearch,
  headerSignIn,
  json,
  mockSearch,
  ROUTES,
  setQuery,
} from "./helpers";
import { scan } from "./axe";
import { expect, test } from "./fixtures";

// Firefox's content process crashes intermittently ("Page crashed") while axe-core analyses some pages,
// mostly the home page: about 30% of attempts locally and 4 of 32 first attempts on GitHub. It is not
// tied to any CSS feature, timing, worker count or axe code path we could isolate (see
// docs/ux-audit/FIREFOX_AXE_CRASH.md). A real accessibility violation is deterministic and fails every
// attempt, so retrying cannot hide one; each retry is recorded as an annotation and reported as flaky.
test.describe.configure({ retries: 3 });
test.afterEach(async ({}, testInfo) => {
  if (testInfo.retry > 0) {
    testInfo.annotations.push({
      type: "axe-retry",
      description: `attempt ${testInfo.retry + 1}: previous attempt failed (see FIREFOX_AXE_CRASH.md)`,
    });
  }
});

const MODES = [
  { name: "phone light", width: 390, scheme: "light" as const },
  { name: "phone dark", width: 390, scheme: "dark" as const },
  { name: "desktop light", width: 1280, scheme: "light" as const },
  { name: "desktop dark", width: 1280, scheme: "dark" as const },
];

// One test per mode and route: a failure names the page, and a slow engine never hits a timeout.
for (const mode of MODES) {
  test.describe(`axe, ${mode.name}`, () => {
    test.use({ viewport: { width: mode.width, height: 800 }, colorScheme: mode.scheme });
    for (const route of [...ROUTES, "/search?q=amox"]) {
      test(route, async ({ page }) => {
        await page.goto(route);
        await expect(headerSignIn(page)).toBeVisible();
        await scan(page, `${route} (${mode.name})`);
      });
    }
  });
}

test.describe("axe: interactive search states", () => {
  test("suggestions open, then no matches", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await mockSearch(page, (route, q) =>
      json(route, q.includes("zzz") ? emptySearch : fixtureSearch("a")),
    );
    await page.goto("/search");
    await setQuery(page, "amox");
    await expect(page.getByRole("option")).toHaveCount(1);
    await scan(page, "search suggestions open");

    await setQuery(page, "zzzz");
    await expect(page.getByRole("status").filter({ hasText: "No results" })).toBeVisible();
    await scan(page, "search no-match state");
  });
});
