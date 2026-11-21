import { headerSignIn, MOCK_USER, mockSignedIn } from "./helpers";
import { expect, test } from "./fixtures";

// Safari-style engines do not Tab to links unless the user enables it (a platform default, not an
// app bug): Playwright's WebKit only ever tabs to form controls. The Tab-walk tests therefore run
// on Chromium and Firefox, and the engine-neutral test below covers every engine.
const WEBKIT_TAB_REASON =
  "WebKit does not Tab to links by default (Safari behaviour); covered by the programmatic focus-visible test";

test.describe("keyboard and focus", () => {
  test("every interactive control in the header and tab bar shows a focus ring (all engines)", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/");
    await expect(headerSignIn(page)).toBeVisible();
    // A keypress first, so :focus-visible treats the following focus() as keyboard-driven.
    await page.keyboard.press("Shift");

    const targets = page.locator(
      'header a, header button, nav[aria-label="Mobile"] a, #global-search, main a',
    );
    const count = Math.min(await targets.count(), 14);
    expect(count).toBeGreaterThan(6);
    for (let i = 0; i < count; i++) {
      const el = targets.nth(i);
      if (!(await el.isVisible())) continue;
      await el.focus();
      const ring = await el.evaluate((e) => {
        const cs = getComputedStyle(e);
        return {
          name: (e.getAttribute("aria-label") || e.textContent || e.id || e.tagName).trim(),
          visible: cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0,
        };
      });
      expect.soft(ring.visible, `"${ring.name.slice(0, 30)}" has a focus ring`).toBe(true);
    }
  });

  for (const width of [390, 1280]) {
    test(`first ten Tab stops show a visible focus outline @ ${width}px`, async ({
      page,
      browserName,
    }) => {
      test.skip(browserName === "webkit", WEBKIT_TAB_REASON);
      await page.setViewportSize({ width, height: 800 });
      await page.goto("/");
      await expect(headerSignIn(page)).toBeVisible();

      const stops: { name: string; outline: boolean; onScreen: boolean }[] = [];
      for (let i = 0; i < 10; i++) {
        await page.keyboard.press("Tab");
        stops.push(
          await page.evaluate(() => {
            const e = document.activeElement as HTMLElement;
            const cs = getComputedStyle(e);
            const r = e.getBoundingClientRect();
            const label = document.querySelector(`label[for="${e.id}"]`)?.textContent;
            return {
              name: (e.getAttribute("aria-label") || label || e.textContent || e.tagName).trim(),
              outline: cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0,
              onScreen: r.width > 0 && r.bottom > 0 && r.top < innerHeight,
            };
          }),
        );
      }
      for (const s of stops) {
        expect.soft(s.outline, `"${s.name}" has a focus outline`).toBe(true);
        expect.soft(s.onScreen, `"${s.name}" is on screen when focused`).toBe(true);
      }
    });
  }

  test("the skip link is the first stop and moves focus into the page", async ({
    page,
    browserName,
  }) => {
    test.skip(browserName === "webkit", WEBKIT_TAB_REASON);
    await page.goto("/");
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Skip to content" });
    await expect(skip).toBeFocused();
    await expect(skip).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#main$/);
  });

  test("the nav that is hidden by the layout is not reachable by keyboard", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "Mobile" })).toBeHidden();
    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 800 });
    await expect(page.getByRole("navigation", { name: "Primary" })).toBeHidden();
    await expect(page.getByRole("navigation", { name: "Mobile" })).toBeVisible();
  });
});

test.describe("reduced motion", () => {
  test("transitions and animations are effectively off", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    const r = await page.evaluate(() => {
      const link = document.querySelector('nav[aria-label="Primary"] a')!;
      const running = [...document.querySelectorAll("*")].filter((e) => {
        const s = getComputedStyle(e);
        return s.animationName !== "none" && parseFloat(s.animationDuration) > 0.05;
      }).length;
      return { transition: parseFloat(getComputedStyle(link).transitionDuration), running };
    });
    expect(r.transition).toBeLessThan(0.05);
    expect(r.running).toBe(0);
  });
});

test.describe("signed out", () => {
  test("shows Sign in and Register, no account controls, and the nav works", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    await expect(headerSignIn(page)).toHaveAttribute("href", "/login");
    await expect(page.getByRole("link", { name: "Register" })).toHaveAttribute("href", "/register");
    await expect(page.getByRole("button", { name: "Sign out" })).toHaveCount(0);

    const primary = page.getByRole("navigation", { name: "Primary" });
    await expect(primary.getByRole("link", { name: "Home" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await primary.getByRole("link", { name: "Calculators" }).click();
    await expect(page).toHaveURL(/\/calculators$/);
    await expect(primary.getByRole("link", { name: "Calculators" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("mobile tab bar navigates and marks the current tab", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/");
    const tabs = page.getByRole("navigation", { name: "Mobile" });
    await tabs.getByRole("link", { name: "Study" }).click();
    await expect(page).toHaveURL(/\/study$/);
    await expect(tabs.getByRole("link", { name: "Study" })).toHaveAttribute("aria-current", "page");
  });
});

test.describe("signed in (mocked user, the API is never asked)", () => {
  for (const width of [390, 768, 1280]) {
    test(`header shows the account controls @ ${width}px`, async ({ page, observed }) => {
      await mockSignedIn(page);
      await page.setViewportSize({ width, height: 800 });
      await page.goto("/");

      const account = page.getByRole("link", { name: MOCK_USER.username });
      const signOut = page.getByRole("button", { name: "Sign out" });
      await expect(account).toBeVisible();
      await expect(signOut).toBeVisible();
      await expect(headerSignIn(page)).toHaveCount(0);
      await expect(page.getByRole("link", { name: "Register" })).toHaveCount(0);

      for (const el of [account, signOut]) {
        const box = (await el.boundingBox())!;
        expect.soft(box.height).toBeGreaterThanOrEqual(44);
      }
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
      expect(observed.expected, "no 403 when the user is signed in").toEqual([]);
    });
  }
});
