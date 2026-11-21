// Tiny stand-in for the Django API so the browser suite needs no database or live data.
// Synthetic fixtures only (names start with FIXTURE-): never real drug, product or regulatory data.
import { createServer } from "node:http";

const PORT = Number(process.env.MOCK_API_PORT ?? 8100);

const json = (res, status, body) => {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
};

createServer((req, res) => {
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

  // Every other list endpoint the tested pages read renders its empty state.
  return json(res, 200, []);
}).listen(PORT, "127.0.0.1", () => console.log(`mock API on ${PORT}`));
