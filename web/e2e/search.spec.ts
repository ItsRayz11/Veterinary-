import type { Page } from "@playwright/test";
import {
  emptySearch,
  fixtureSearch,
  json,
  mockSearch,
  searchInput,
  setQuery,
  sleep,
} from "./helpers";
import { expect, test } from "./fixtures";

const options = (page: Page) => page.getByRole("option");
const liveRegion = (page: Page) => page.locator("[aria-live=polite]");

test.describe("search box reflects the URL", () => {
  const cases: [string, string][] = [
    ["amox", "amox"],
    ["amoxicillin%20clavulanate", "amoxicillin clavulanate"],
    ["amoxicillin+clavulanate", "amoxicillin clavulanate"],
    ["caf%C3%A9", "café"],
    ["a%26b%3Dc%2B%2F%3F%23%22%3C%3E%27", "a&b=c+/?#\"<>'"],
    ["%3Cscript%3Ealert(1)%3C%2Fscript%3E", "<script>alert(1)</script>"],
  ];
  for (const [encoded, expected] of cases) {
    test(`q=${encoded}`, async ({ page }) => {
      await page.goto(`/search?q=${encoded}`);
      await expect(searchInput(page)).toHaveValue(expected);
      expect(await page.locator("main script").count(), "query must never become markup").toBe(0);
    });
  }

  test("empty query: empty input, no clear button", async ({ page }) => {
    await page.goto("/search");
    await expect(searchInput(page)).toHaveValue("");
    await expect(page.getByRole("button", { name: "Clear search" })).toHaveCount(0);
    await page.goto("/search?q=");
    await expect(searchInput(page)).toHaveValue("");
  });

  test("one-character query is shown and the page asks for two", async ({ page }) => {
    await page.goto("/search?q=a");
    await expect(searchInput(page)).toHaveValue("a");
    await expect(page.getByText("Type at least 2 characters.")).toBeVisible();
  });

  test("a URL-seeded query does not fetch suggestions or open a dropdown on load", async ({
    page,
  }) => {
    let calls = 0;
    await mockSearch(page, (route) => {
      calls++;
      return json(route, fixtureSearch("x"));
    });
    await page.goto("/search?q=amox");
    await sleep(800);
    expect(calls).toBe(0);
    await expect(page.getByRole("listbox")).toHaveCount(0);
    // Typing does fetch.
    await searchInput(page).press("End");
    await searchInput(page).pressSequentially("i");
    await expect(options(page)).toHaveCount(1);
  });
});

test("submit, back and forward keep the input in step with the URL", async ({ page }) => {
  await mockSearch(page, (route) => json(route, fixtureSearch("x")));
  await page.goto("/search?q=aaa");
  await setQuery(page, "bbb");
  await searchInput(page).press("Enter");
  await expect(page).toHaveURL(/\/search\?q=bbb$/);
  await expect(searchInput(page)).toHaveValue("bbb");

  await page.goBack();
  await expect(page).toHaveURL(/\/search\?q=aaa$/);
  await expect(searchInput(page)).toHaveValue("aaa");

  await page.goForward();
  await expect(page).toHaveURL(/\/search\?q=bbb$/);
  await expect(searchInput(page)).toHaveValue("bbb");
});

test.describe("asynchronous behaviour", () => {
  test("a slow response cannot overwrite a newer one, and loading is announced", async ({
    page,
  }) => {
    await mockSearch(page, async (route, q) => {
      if (q.startsWith("slow")) await sleep(1500);
      return json(route, fixtureSearch(q.startsWith("slow") ? "SLOW" : "FAST"));
    });
    await page.goto("/search");
    await setQuery(page, "slow");
    await expect(liveRegion(page)).toContainText("Searching");

    await setQuery(page, "fast");
    await expect(options(page)).toContainText("FIXTURE-FAST");
    await sleep(2000); // the slow response lands now
    await expect(options(page)).toHaveCount(1);
    await expect(options(page)).toContainText("FIXTURE-FAST");
    await expect(liveRegion(page)).not.toContainText("Searching");
  });

  test("rapid typing ends on the final query only", async ({ page }) => {
    await mockSearch(page, async (route, q) => {
      if (q.length < 4) await sleep(900);
      return json(route, fixtureSearch(q));
    });
    await page.goto("/search");
    await searchInput(page).click();
    for (const ch of "dogs") {
      await page.keyboard.type(ch);
      await sleep(260);
    }
    await expect(options(page)).toHaveCount(1);
    await expect(options(page)).toContainText("FIXTURE-dogs");
    await sleep(1200);
    await expect(options(page)).toContainText("FIXTURE-dogs");
  });

  test("a failed request is announced and the next keystroke recovers", async ({
    page,
    tolerate,
  }) => {
    tolerate(/500 \/api\/v1\/search/); // provoked on purpose
    let fail = true;
    await mockSearch(page, (route) =>
      fail ? route.fulfill({ status: 500, body: "boom" }) : json(route, fixtureSearch("OK")),
    );
    await page.goto("/search");
    await setQuery(page, "fail");
    await expect(liveRegion(page)).toContainText("Search is unavailable right now.");
    await expect(liveRegion(page)).not.toContainText("Searching");

    fail = false;
    await searchInput(page).pressSequentially("s");
    await expect(options(page)).toContainText("FIXTURE-OK");
    await expect(liveRegion(page)).not.toContainText("unavailable");
  });
});

test.describe("clearing", () => {
  test("clear empties the box, restores focus and ignores in-flight responses", async ({
    page,
  }) => {
    await mockSearch(page, async (route) => {
      await sleep(1200);
      return json(route, fixtureSearch("LATE"));
    });
    await page.goto("/search");
    await setQuery(page, "clearme");
    const clear = page.getByRole("button", { name: "Clear search" });
    await expect(clear).toBeVisible();
    await clear.click();

    await expect(searchInput(page)).toHaveValue("");
    await expect(searchInput(page)).toBeFocused();
    await expect(liveRegion(page)).not.toContainText("Searching");
    await sleep(1800);
    await expect(options(page)).toHaveCount(0);
    await expect(searchInput(page)).toHaveValue("");
    await expect(clear).toHaveCount(0);
  });

  test("the input and clear button are touch sized", async ({ page }) => {
    await page.goto("/search?q=amox");
    const input = await searchInput(page).boundingBox();
    const clear = await page.getByRole("button", { name: "Clear search" }).boundingBox();
    expect(input!.height).toBeGreaterThanOrEqual(44);
    expect(clear!.height).toBeGreaterThanOrEqual(40);
    expect(clear!.width).toBeGreaterThanOrEqual(40);
  });
});

test.describe("keyboard and ARIA", () => {
  test("arrow keys move the active option, Escape closes the list", async ({ page }) => {
    await mockSearch(page, (route) =>
      json(route, {
        ...emptySearch,
        generics: [
          { name: "FIXTURE-A", slug: "a" },
          { name: "FIXTURE-B", slug: "b" },
        ],
      }),
    );
    await page.goto("/search");
    await setQuery(page, "fix");
    await expect(options(page)).toHaveCount(2);
    await searchInput(page).press("ArrowDown");
    await searchInput(page).press("ArrowDown");
    const activeId = await searchInput(page).getAttribute("aria-activedescendant");
    await expect(page.locator(`[id="${activeId}"]`)).toContainText("FIXTURE-B");
    await searchInput(page).press("Escape");
    await expect(options(page)).toHaveCount(0);
  });

  test("no matches: no empty listbox (valid ARIA), message is a status region", async ({
    page,
  }) => {
    await mockSearch(page, (route) => json(route, emptySearch));
    await page.goto("/search");
    await setQuery(page, "zzzz");
    await expect(page.getByRole("status").filter({ hasText: "No results" })).toBeVisible();
    await expect(page.getByRole("listbox")).toHaveCount(0);
    await expect(searchInput(page)).toHaveAttribute("aria-expanded", "false");
  });
});
