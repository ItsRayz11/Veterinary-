import { expect, test } from "./fixtures";

// Looping skeleton/loader animations must stop looping when the visitor asks for reduced motion.
test("reduced motion: the skeleton pulse does not loop", async ({ browser, baseURL }) => {
  for (const [reduce, expected] of [
    ["reduce", "1"],
    ["no-preference", "infinite"],
  ] as const) {
    const ctx = await browser.newContext({
      baseURL,
      reducedMotion: reduce,
      serviceWorkers: "block",
    });
    const page = await ctx.newPage();
    await page.goto("/offline");
    const count = await page.evaluate(() => {
      const d = document.createElement("div");
      d.className = "animate-pulse";
      document.body.appendChild(d);
      return getComputedStyle(d).animationIterationCount;
    });
    expect(count, `reducedMotion=${reduce}`).toBe(expected);
    await ctx.close();
  }
});
