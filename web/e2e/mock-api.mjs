// Tiny stand-in for the Django API so the browser suite needs no database or live data.
// Synthetic fixtures only (names start with FIXTURE-): never real drug, product or regulatory data.
import { createServer } from "node:http";

const PORT = Number(process.env.MOCK_API_PORT ?? 8100);
// Test-only behaviours, off by default: MOCK_API_FAIL=1 answers every data request with a 503, and
// MOCK_API_DELAY_MS adds latency, so error and slow-loading states can be exercised for real.
const FAIL = process.env.MOCK_API_FAIL === "1";
const DELAY_MS = Number(process.env.MOCK_API_DELAY_MS ?? 0);
const UNKNOWN_SLUG = /^\/api\/v1\/[a-z-]+\/missing-[a-z0-9-]+\/?$/;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// "connection: close": the app's proxy otherwise reuses pooled keep-alive sockets that Node closes after
// 5 s idle, and the occasional reused-just-closed socket surfaces as a spurious 500 on /api/v1/*.
const json = (res, status, body) => {
  res.writeHead(status, { "content-type": "application/json", connection: "close" });
  res.end(JSON.stringify(body));
};

createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", "http://mock");
  if (url.pathname === "/health") return json(res, 200, { ok: true });
  if (req.method !== "GET")
    return json(res, 405, { detail: "Method not allowed (mock API is read-only)." });

  // Signed-out visitor: same as the real API (DRF session auth answers 403).
  if (url.pathname.startsWith("/api/v1/auth/me")) {
    return json(res, 403, { detail: "Authentication credentials were not provided." });
  }

  if (url.pathname.startsWith("/api/v1/search")) {
    const q = (url.searchParams.get("q") ?? "").trim();
    const empty = { generics: [], products: [], companies: [], did_you_mean: [] };
    if (q.length < 2 || q.toLowerCase().includes("nomatch")) return json(res, 200, empty);
    return json(res, 200, {
      ...empty,
      generics: [{ name: `FIXTURE-${q}`, slug: `fixture-${q.toLowerCase().replace(/\W+/g, "-")}` }],
    });
  }

  if (DELAY_MS) await sleep(DELAY_MS);
  if (FAIL) return json(res, 503, { detail: "Mock API is in failure mode." });
  // A record that does not exist: the real API answers JSON 404, which the app turns into notFound().
  if (UNKNOWN_SLUG.test(url.pathname)) return json(res, 404, { detail: "Not found." });

  // Every other list endpoint the tested pages read renders its empty state.
  return json(res, 200, []);
}).listen(PORT, "127.0.0.1", () => console.log(`mock API on ${PORT}`));
