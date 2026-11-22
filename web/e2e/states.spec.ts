import { expect, test } from "./fixtures";
import { startStack, type Stack } from "./stack";

// These start their own app copies (a failing and a slow backend), so they run on one engine to keep
// CI time down; the behaviour under test is engine-independent (HTTP status, DOM, CSS).
test.skip(({ browserName }) => browserName !== "chromium", "stack tests run on Chromium only");

test.describe("record that does not exist", () => {
  // Guards a deliberate behaviour: unknown slugs must answer a real HTTP 404 (not a streamed 200
  // soft-404), which is why navigation progress is done on the client and not with loading.tsx.
  for (const path of [
    "/species/missing-x",
    "/drugs/missing-x",
    "/companies/missing-x",
    "/products/missing-x",
  ]) {
    test(`${path} answers 404 with a Not found page`, async ({ page, tolerate }) => {
      tolerate(/404 \/(species|drugs|companies|products)\/missing-x/);
      const res = await page.goto(path);
      expect(res!.status()).toBe(404);
      await expect(page.getByRole("heading", { name: "Not found" })).toBeVisible();
    });
  }
});

test.describe("slow data service", () => {
  let stack: Stack;
  test.beforeAll(async () => {
    test.setTimeout(150_000);
    stack = await startStack({ delayMs: 2000 });
  });
  test.afterAll(async () => stack?.stop());

  test("a tap shows progress straight away, then the page arrives and progress goes", async ({
    browser,
  }) => {
    const ctx = await browser.newContext({
      baseURL: stack.baseURL,
      viewport: { width: 390, height: 800 },
      serviceWorkers: "block",
    });
    const page = await ctx.newPage();
    await page.goto("/");
    await expect(page.getByRole("banner").getByRole("link", { name: "Sign in" })).toBeVisible();
    // Let the link prefetch settle so the wait below is the real server render.
    await page.waitForTimeout(1000);

    const started = Date.now();
    await page
      .getByRole("navigation", { name: "Mobile" })
      .getByRole("link", { name: "Universities" })
      .click();

    const bar = page.getByTestId("nav-progress");
    await expect(bar).toHaveCount(1);
    await expect(bar).toHaveCSS("opacity", "1", { timeout: 1000 }); // faded in after its 120 ms delay
    expect(new URL(page.url()).pathname, "still on the old page while loading").toBe("/");
    await expect(page.getByRole("status").filter({ hasText: "Loading page" })).toHaveCount(1, {
      timeout: 1500,
    });

    await expect(page.getByRole("heading", { name: "Veterinary universities" })).toBeVisible({
      timeout: 20_000,
    });
    expect(Date.now() - started, "the backend really was slow").toBeGreaterThan(1500);
    await expect(bar).toHaveCount(0);
    await expect(page.getByRole("status").filter({ hasText: "Loading page" })).toHaveCount(0);
    await ctx.close();
  });

  test("reduced motion: the bar is static, not sliding", async ({ browser }) => {
    const ctx = await browser.newContext({
      baseURL: stack.baseURL,
      viewport: { width: 390, height: 800 },
      reducedMotion: "reduce",
      serviceWorkers: "block",
    });
    const page = await ctx.newPage();
    await page.goto("/");
    await expect(page.getByRole("banner").getByRole("link", { name: "Sign in" })).toBeVisible();
    await page.waitForTimeout(1000);
    await page
      .getByRole("navigation", { name: "Mobile" })
      .getByRole("link", { name: "Jobs" })
      .click();
    const bar = page.getByTestId("nav-progress");
    await expect(bar).toHaveCount(1);
    const anim = await bar.evaluate((e) => getComputedStyle(e, "::before").animationName);
    expect(anim).toBe("none");
    await ctx.close();
  });
});

test.describe("data service down", () => {
  let stack: Stack;
  test.beforeAll(async () => {
    test.setTimeout(150_000);
    stack = await startStack({ fail: true });
  });
  test.afterAll(async () => stack?.stop());

  test("a data page explains what happened and offers a way forward; pages without data still work", async ({
    browser,
  }) => {
    const ctx = await browser.newContext({ baseURL: stack.baseURL, serviceWorkers: "block" });
    const page = await ctx.newPage();

    const res = await page.goto("/species");
    expect(res!.status(), "outage is not disguised as success").toBeGreaterThanOrEqual(500);
    const alert = page.getByRole("alert").filter({ hasText: "Something went wrong" });
    await expect(alert).toContainText("could not be loaded");
    await expect(alert).toContainText("data service may be temporarily unavailable");
    await expect(alert).not.toContainText("has been lost");

    const retry = page.getByRole("button", { name: "Try again" });
    const home = page.getByRole("link", { name: "Go to the home page" });
    for (const el of [retry, home]) {
      const box = (await el.boundingBox())!;
      expect(box.height).toBeGreaterThanOrEqual(44);
    }
    await retry.click(); // still down: it must fail gracefully, not crash
    await expect(alert).toBeVisible();

    await home.click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "Veterinary drug reference" })).toBeVisible();
    await ctx.close();
  });
});
