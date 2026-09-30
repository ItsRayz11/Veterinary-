// Real-browser check of two-factor sign-in (manual, Windows).
// Setup:  npm i --no-save puppeteer-core; build + `next start -p 3100`; API on :8000 (scratch DB).
// Run:    node web/scripts/mfa-check.mjs
// Registers a throw-away user, turns on 2FA through the UI, then signs in again in a fresh browser
// context: wrong code refused, recovery code accepted, the same recovery code refused a second time.
import puppeteer from "puppeteer-core";
import { createHmac } from "node:crypto";

const BASE = process.env.BASE_URL ?? "http://localhost:3100";
const B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
const totp = (secret, step = Math.floor(Date.now() / 30000)) => {
  let bits = "";
  for (const c of secret.replace(/=+$/, "").toUpperCase()) bits += B32.indexOf(c).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const msg = Buffer.alloc(8);
  msg.writeBigUInt64BE(BigInt(step));
  const h = createHmac("sha1", key).update(msg).digest();
  const o = h[h.length - 1] & 15;
  return String(((h.readUInt32BE(o) & 0x7fffffff) % 1_000_000)).padStart(6, "0");
};

let failed = 0;
const ok = (name, cond) => {
  if (!cond) failed += 1;
  console.log(`${cond ? "PASS" : "FAIL"}  ${name}`);
};
const browser = await puppeteer.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: ["--no-sandbox", "--disable-gpu"],
});
const text = (page) => page.evaluate(() => document.body.innerText);
const clickButton = (page, label) =>
  page.evaluate((l) => [...document.querySelectorAll("button")].find((b) => b.innerText.includes(l))?.click(), label);

const user = `mfa${Date.now().toString(36)}`;
const password = "a-long-unusual-passphrase-9";

// 1. Register and turn 2FA on
let page = await browser.newPage();
await page.goto(`${BASE}/register`, { waitUntil: "networkidle0" });
await page.type("#username", user);
await page.type("#email", `${user}@example.com`);
await page.type("#password", password);
await Promise.all([page.waitForNavigation({ waitUntil: "networkidle0" }).catch(() => {}), page.click("button[type=submit]")]);
await page.goto(`${BASE}/account`, { waitUntil: "networkidle0" });
await page.waitForFunction(() => document.body.innerText.includes("Set up two-factor"), { timeout: 10000 });
await clickButton(page, "Set up two-factor");
await page.waitForSelector("#mfa-code", { timeout: 10000 });
const secret = await page.evaluate(() => document.querySelector("p.font-mono")?.textContent?.trim() ?? "");
ok("setup shows a secret", /^[A-Z2-7]{16,}$/.test(secret.replace(/\s/g, "")));
await page.type("#mfa-code", totp(secret.replace(/\s/g, "")));
await clickButton(page, "Turn on");
await page.waitForFunction(() => document.body.innerText.includes("Save your recovery codes"), { timeout: 10000 });
const codes = await page.$$eval("ul.font-mono li", (els) => els.map((e) => e.textContent.trim()));
ok("ten recovery codes shown", codes.length === 10);
await page.close();

// 2. Sign in again in a clean context
async function attempt(code) {
  const ctx = await browser.createBrowserContext();
  const p = await ctx.newPage();
  await p.goto(`${BASE}/login`, { waitUntil: "networkidle0" });
  await p.type("#username", user);
  await p.type("#password", password);
  await p.click("button[type=submit]");
  await p.waitForSelector("#code", { timeout: 10000 });
  const asked = (await text(p)).includes("Two-factor code");
  await p.type("#code", code);
  await p.click("button[type=submit]");
  await new Promise((r) => setTimeout(r, 2500));
  const t = await text(p);
  const signedIn = !(await p.$("#code")) && !t.includes("Sign in\nUsername");
  await ctx.close();
  return { asked, signedIn, t };
}
const wrong = await attempt("000000");
ok("password alone does not sign in: a code is asked for", wrong.asked);
ok("wrong code refused", !wrong.signedIn);
const good = await attempt(codes[0]);
ok("recovery code accepted", good.signedIn);
const again = await attempt(codes[0]);
ok("the same recovery code is refused the second time", !again.signedIn);

await browser.close();
console.log(failed ? `\n${failed} check(s) failed` : "\nAll two-factor checks passed");
process.exit(failed ? 1 : 0);
