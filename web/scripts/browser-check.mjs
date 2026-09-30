// Real-browser end-to-end check (manual, Windows): calculators, service worker, true offline.
// Setup:  npm i --no-save puppeteer-core  (uses your installed Chrome)
// Run:    build the web app, start it with `next start -p 3100`, then `node web/scripts/browser-check.mjs`.
// It STOPS the server on port 3100 midway on purpose, to prove offline behaviour.
import puppeteer from "puppeteer-core";
import { execSync } from "node:child_process";

const BASE = "http://localhost:3100";
const results = [];
const ok = (name, cond, extra = "") => {
  results.push({ name, pass: !!cond });
  console.log(`${cond ? "PASS" : "FAIL"}  ${name}${extra ? "  " + extra : ""}`);
};

const browser = await puppeteer.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: ["--no-sandbox", "--disable-gpu"],
});
const page = await browser.newPage();
const consoleErrors = [];
page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
page.on("pageerror", (e) => consoleErrors.push(String(e)));

// 1. Calculator computes in the browser under the CSP
await page.goto(`${BASE}/calculators/dilution`, { waitUntil: "networkidle0" });
await page.type("#stock_conc", "10");
await page.type("#target_conc", "2");
await page.type("#final_volume_ml", "100");
await page.waitForFunction(() => document.body.innerText.includes("Stock solution"), { timeout: 5000 });
const text = await page.evaluate(() => document.body.innerText);
ok("dilution: 20.00 mL stock", text.includes("20.00 mL"));
ok("dilution: 80.00 mL diluent", text.includes("80.00 mL"));

// 2. Impossible input gives a readable error, not a crash
await page.$eval("#target_conc", (el) => (el.value = ""));
await page.type("#target_conc", "50");
await page.waitForFunction(() => document.body.innerText.includes("cannot be higher"), { timeout: 5000 });
ok("dilution: impossible input explained", true);

// 3. Service worker registers and precaches calculators + their chunks
await page.evaluate(() => navigator.serviceWorker.ready);
await new Promise((r) => setTimeout(r, 6000));
const cached = await page.evaluate(async () => {
  const names = await caches.keys();
  const out = {};
  for (const n of names) out[n] = (await (await caches.open(n)).keys()).map((r) => new URL(r.url).pathname);
  return out;
});
const pages = Object.entries(cached).find(([k]) => k.includes("pages"))?.[1] ?? [];
const statics = Object.entries(cached).find(([k]) => k.includes("static"))?.[1] ?? [];
ok("sw: offline page cached", pages.includes("/offline"));
ok("sw: calculators precached", pages.includes("/calculators/dilution") && pages.includes("/calculators/cri"), `(${pages.length} pages)`);
ok("sw: JS chunks cached", statics.length > 3, `(${statics.length} assets)`);
ok("sw: no private paths cached", !pages.some((p) => /^\/(api|account|admin|login|register|ask)/.test(p)));

// 4. Offline: calculators still work; private pages do not come from cache
// Really remove the network: stop the server (page.setOfflineMode does not affect the service worker).
execSync('powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 3100 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"');
await new Promise((r) => setTimeout(r, 1500));
const serverGone = await fetch(BASE).then(() => false, () => true);
ok("network really gone (server stopped)", serverGone);
await page.setOfflineMode(true);
await page.goto(`${BASE}/calculators/cri`, { waitUntil: "domcontentloaded" });
const heading = await page.$eval("h1", (el) => el.textContent);
ok("offline: CRI calculator page loads", /CRI/i.test(heading), heading);
await page.type("#dose_mcg_per_kg_min", "2");
await page.type("#concentration_mg_per_ml", "1");
await page.type("#weight", "10");
await page.waitForFunction(() => document.body.innerText.includes("Pump rate"), { timeout: 5000 });
const offlineText = await page.evaluate(() => document.body.innerText);
ok("offline: CRI computes 1.20 mL/h", offlineText.includes("1.20 mL/h"));
await page.goto(`${BASE}/species/dog`, { waitUntil: "domcontentloaded" }).catch(() => null);
const offlineBody = await page.evaluate(() => document.body.innerText);
ok("offline: uncached page shows the offline page", /You are offline/.test(offlineBody));
await page.goto(`${BASE}/account`, { waitUntil: "domcontentloaded" }).catch(() => null);
const accountBody = await page.evaluate(() => document.body.innerText).catch(() => "");
ok("offline: /account is never served from cache", !/Account/.test(accountBody) || /offline|ERR|can.t be reached/i.test(accountBody));
await page.setOfflineMode(false);

ok("no console errors / CSP violations", consoleErrors.filter((e) => !/Failed to load resource|net::ERR/.test(e)).length === 0, consoleErrors.slice(0, 2).join(" | "));

await browser.close();
const failed = results.filter((r) => !r.pass);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
