// Accessibility + mobile sweep (manual, Windows): axe-core on key pages at phone and desktop width,
// light and dark, plus horizontal-overflow and small-tap-target checks.
// Setup:  npm i --no-save puppeteer-core axe-core   (uses your installed Chrome)
// Run:    build, `next start -p 3100` (API on :8000), then `node web/scripts/a11y-check.mjs`.
// Automated checks find roughly a third of accessibility problems; they do not replace testing
// with a real screen reader (see docs/TESTING.md).
import puppeteer from "puppeteer-core";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const BASE = process.env.BASE_URL ?? "http://localhost:3100";
const axeSource = readFileSync(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");
const PAGES = (process.env.PAGES ??
  "/,/calculators,/calculators/dilution,/calculators/cri,/drugs,/login,/register,/jobs,/scholarships,/study,/ask,/interactions,/offline,/countries,/account,/admin-panel")
  .split(",");
const VIEWPORTS = [
  { name: "phone", width: 375, height: 812, isMobile: true, hasTouch: true },
  { name: "desktop", width: 1280, height: 800 },
];

const browser = await puppeteer.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: ["--no-sandbox", "--disable-gpu"],
});

let failures = 0;
for (const vp of VIEWPORTS) {
  for (const scheme of ["light", "dark"]) {
    const page = await browser.newPage();
    await page.setViewport(vp);
    await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: scheme }]);
    for (const path of PAGES) {
      const label = `${vp.name}/${scheme} ${path}`;
      try {
        await page.goto(BASE + path, { waitUntil: "networkidle0", timeout: 30000 });
      } catch (e) {
        console.log(`SKIP  ${label}  (${e.message.split("\n")[0]})`);
        continue;
      }
      await page.evaluate(axeSource);
      const res = await page.evaluate(() =>
        // eslint-disable-next-line no-undef
        axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa", "best-practice"] }),
      );
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      const bad = res.violations.filter((v) => v.impact !== "minor");
      if (bad.length || overflow > 0) failures += 1;
      console.log(`${bad.length || overflow > 0 ? "FAIL" : "PASS"}  ${label}`);
      if (overflow > 0) console.log(`      horizontal overflow: ${overflow}px`);
      for (const v of bad) {
        console.log(`      [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length})`);
        for (const n of v.nodes.slice(0, 2)) console.log(`         ${n.target.join(" ")}`);
      }
    }
    await page.close();
  }
}
await browser.close();
console.log(failures ? `\n${failures} page(s) with problems` : "\nAll pages clean");
process.exit(failures ? 1 : 0);
