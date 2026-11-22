import { defineConfig, devices } from "@playwright/test";

/**
 * Browser regression suite. Everything runs against a production build (`npm run build` first)
 * served by `next start`, with the server-side API pointed at e2e/mock-api.mjs: no Django, no
 * database, no live data, no credentials. Browser-side /api/v1 calls reach the same mock through
 * the app's own proxy, and individual tests override them with page.route().
 */
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 3100);
const API_PORT = Number(process.env.E2E_API_PORT ?? 8100);
const CI = !!process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  workers: CI ? 2 : undefined,
  timeout: 60_000,
  expect: { timeout: 7_000 },
  reporter: CI
    ? [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]]
    : [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    // Traces are recorded on the retry only: recording response bodies on every first run made
    // Firefox teardown time out on slow machines.
    trace: "on-first-retry",
    // page.route() cannot see requests a Service Worker handles (documented Playwright
    // limitation), which made mocked responses unreliable in WebKit. The worker's logic has its
    // own unit tests (src/lib/sw.test.ts).
    serviceWorkers: "block",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  webServer: [
    {
      command: "node e2e/mock-api.mjs",
      url: `http://127.0.0.1:${API_PORT}/health`,
      env: { MOCK_API_PORT: String(API_PORT) },
      reuseExistingServer: !CI,
      timeout: 30_000,
    },
    {
      command: `npx next start -p ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}/offline`,
      env: { API_URL: `http://127.0.0.1:${API_PORT}`, NEXT_TELEMETRY_DISABLED: "1" },
      reuseExistingServer: !CI,
      timeout: 120_000,
    },
  ],
});
