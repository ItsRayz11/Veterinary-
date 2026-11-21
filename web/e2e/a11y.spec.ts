import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import {
  emptySearch,
  fixtureSearch,
  headerSignIn,
  json,
  mockSearch,
  ROUTES,
  setQuery,
} from "./helpers";
import { expect, test } from "./fixtures";

async function scan(page: Page, label: string) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  const summary = violations.map(
    (v) => `[${v.impact}] ${v.id} (${v.nodes.length}): ${v.nodes[0]?.target.join(" ")}`,
  );
  expect(summary, `axe violations on ${label}`).toEqual([]);
}

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
