import { CALCULATOR_SLUGS } from "../src/lib/calc/slugs";
import { scan } from "./axe";
import { headerSignIn, waitForHydration } from "./helpers";
import { expect, test } from "./fixtures";

/**
 * Browser-level checks for the calculators. They never assert clinical values: the only numbers are
 * the plain dilution arithmetic (C1 x V1 = C2 x V2) that the repo's own scripts/browser-check.mjs
 * already asserts. Formulas and their unit tests live in src/lib/calc and are not touched here.
 */
const BAD = /NaN|Infinity|undefined|\[object|null/;

for (const slug of CALCULATOR_SLUGS) {
  test.describe(`calculator: ${slug}`, () => {
    test("loads, every numeric field has an accessible name, results sit in a live region", async ({
      page,
    }) => {
      const res = await page.goto(`/calculators/${slug}`);
      expect(res!.status()).toBe(200);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

      const fields = page.locator('main input[inputmode="decimal"]');
      expect(await fields.count(), "has numeric inputs").toBeGreaterThan(0);
      for (let i = 0; i < (await fields.count()); i++) {
        await expect(fields.nth(i)).toHaveAccessibleName(/\S/);
      }
      await expect(page.locator('main [aria-live="polite"]')).toHaveCount(1);
    });

    test("blank, zero, negative, text and absurd values never show NaN/Infinity or throw", async ({
      page,
    }) => {
      await page.goto(`/calculators/${slug}`);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const fields = page.locator('main input[inputmode="decimal"]');
      await waitForHydration(fields.first()); // otherwise nothing is calculated and the check proves nothing
      const count = await fields.count();

      for (const value of ["", "0", "-5", "abc", "1e309", "99999999999999999999", "0.0000001"]) {
        for (let i = 0; i < count; i++) await fields.nth(i).fill(value);
        const text = await page.locator("main").innerText();
        expect(text, `value "${value}"`).not.toMatch(BAD);
      }
    });

    // Firefox's content process crashes or hangs intermittently under axe (see
    // docs/ux-audit/FIREFOX_AXE_CRASH.md). A real violation fails every attempt, so retries cannot hide
    // one; they are reported as flaky.
    test.describe("axe", () => {
      test.describe.configure({ retries: 3 });
      test("finds no violations (phone, light)", async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 800 });
        await page.goto(`/calculators/${slug}`);
        await expect(headerSignIn(page)).toBeVisible();
        await scan(page, `/calculators/${slug}`);
      });
    });
  });
}

test.describe("dilution calculator (plain arithmetic, as in scripts/browser-check.mjs)", () => {
  test("10 / 2 / 100 gives 20.00 mL stock and 80.00 mL diluent, with units", async ({ page }) => {
    await page.goto("/calculators/dilution");
    await waitForHydration(page.locator("#stock_conc"));
    await page.locator("#stock_conc").fill("10");
    await page.locator("#target_conc").fill("2");
    await page.locator("#final_volume_ml").fill("100");
    const result = page.locator('main [aria-live="polite"]');
    await expect(result).toContainText("20.00 mL");
    await expect(result).toContainText("80.00 mL");
  });

  test("an impossible target is explained in words, as an alert, and clears when fixed", async ({
    page,
  }) => {
    await page.goto("/calculators/dilution");
    await waitForHydration(page.locator("#stock_conc"));
    await page.locator("#stock_conc").fill("10");
    await page.locator("#target_conc").fill("50");
    await page.locator("#final_volume_ml").fill("100");
    const alert = page.getByRole("alert").filter({ hasText: "cannot be higher" });
    await expect(alert).toBeVisible();

    await page.locator("#target_conc").fill("2");
    await expect(alert).toHaveCount(0);
    await expect(page.locator('main [aria-live="polite"]')).toContainText("20.00 mL");
  });
});
