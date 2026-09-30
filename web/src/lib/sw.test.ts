import { readFileSync } from "node:fs";
import { join } from "node:path";
import vm from "node:vm";
import { beforeEach, describe, expect, it } from "vitest";

type Listener = (event: Record<string, unknown>) => void;

/** Runs public/sw.js against an in-memory Cache API and a scriptable network. */
function loadWorker() {
  const listeners: Record<string, Listener> = {};
  const stores = new Map<string, Map<string, Response>>();
  const fetched: string[] = [];
  const network = { online: true, delay: 0, status: 200, pages: {} as Record<string, string> };

  const key = (r: Request | string) =>
    typeof r === "string" ? new URL(r, "https://site.test").href : r.url;
  const caches = {
    open: async (name: string) => {
      if (!stores.has(name)) stores.set(name, new Map());
      const s = stores.get(name)!;
      return {
        match: async (r: Request | string) => s.get(key(r))?.clone(),
        put: async (r: Request | string, res: Response) => void s.set(key(r), res),
        add: async (r: string) => void s.set(key(r), new Response("cached " + r)),
        delete: async (r: Request | string) => s.delete(key(r)),
        keys: async () => [...s.keys()].map((u) => new Request(u)),
      };
    },
    keys: async () => [...stores.keys()],
    delete: async (n: string) => stores.delete(n),
  };
  const fakeFetch = async (input: Request | string) => {
    const url = key(input);
    fetched.push(new URL(url).pathname);
    if (network.delay) await new Promise((r) => setTimeout(r, network.delay));
    if (!network.online) throw new TypeError("offline");
    const path = new URL(url).pathname;
    const body = network.pages[path] ?? `network ${path}`;
    const res = new Response(body, { status: network.status });
    Object.defineProperty(res, "type", { value: "basic" });
    return res;
  };

  const self = {
    location: { origin: "https://site.test" },
    addEventListener: (type: string, fn: Listener) => void (listeners[type] = fn),
    skipWaiting: async () => undefined,
    clients: { claim: async () => undefined },
  };
  // Shorten the navigation timeout so slow-network behaviour can be tested quickly.
  const source = readFileSync(join(process.cwd(), "public", "sw.js"), "utf8").replace(
    "const NAV_TIMEOUT_MS = 4000;",
    "const NAV_TIMEOUT_MS = 50;",
  );
  vm.runInNewContext(source, {
    self,
    caches,
    fetch: fakeFetch,
    Response,
    Request,
    URL,
    Promise,
    setTimeout,
    clearTimeout,
    Set,
    Array,
    Error,
  });

  /** Dispatch a fetch event; returns the response, or null when the worker did not intercept. */
  async function request(
    path: string,
    mode: "navigate" | "same-origin" = "navigate",
    method = "GET",
  ) {
    let handled: Promise<Response> | null = null;
    const req = new Request(new URL(path, "https://site.test"), { method });
    Object.defineProperty(req, "mode", { value: mode });
    listeners.fetch({ request: req, respondWith: (p: Promise<Response>) => (handled = p) });
    return handled ? await (handled as Promise<Response>) : null;
  }
  async function send(type: string, data?: unknown) {
    let waited: Promise<unknown> = Promise.resolve();
    listeners[type]({ data, waitUntil: (p: Promise<unknown>) => (waited = p) });
    await waited;
  }
  return { request, send, network, stores, fetched };
}

describe("service worker", () => {
  let sw: ReturnType<typeof loadWorker>;
  beforeEach(async () => {
    sw = loadWorker();
    await sw.send("install");
  });

  it.each([
    "/api/v1/auth/me",
    "/admin-panel",
    "/admin/login/",
    "/account",
    "/login",
    "/register",
    "/ask",
    "/study/exams/12",
    "/study/flashcards",
    "/jobs/new",
  ])("never touches %s", async (path) => {
    expect(await sw.request(path)).toBeNull();
  });

  it("does not intercept non-GET requests or cross-origin URLs", async () => {
    expect(await sw.request("/calculators", "navigate", "POST")).toBeNull();
    expect(await sw.request("https://elsewhere.test/x")).toBeNull();
  });

  it("caches public pages and serves them when the network is down", async () => {
    sw.network.pages["/drugs/enrofloxacin"] = "fresh drug page";
    const online = await sw.request("/drugs/enrofloxacin");
    expect(await online!.text()).toBe("fresh drug page");
    sw.network.online = false;
    const offline = await sw.request("/drugs/enrofloxacin");
    expect(await offline!.text()).toBe("fresh drug page");
  });

  it("falls back to the offline page for pages it never saw, and never caches private ones", async () => {
    sw.network.online = false;
    const res = await sw.request("/species/dog");
    expect(await res!.text()).toBe("cached /offline");
    sw.network.online = true;
    await sw.request("/study/exams/3"); // not intercepted
    const pages = sw.stores.get("vetref-pages-v1")!;
    expect([...pages.keys()].some((k) => k.includes("/study/exams"))).toBe(false);
  });

  it("serves static assets cache-first", async () => {
    await sw.request("/_next/static/chunks/a.js", "same-origin");
    sw.fetched.length = 0;
    const again = await sw.request("/_next/static/chunks/a.js", "same-origin");
    expect(await again!.text()).toBe("network /_next/static/chunks/a.js");
    expect(sw.fetched).toEqual([]); // second read never hit the network
  });

  it("precaches calculators and their chunks but ignores private or invalid paths", async () => {
    sw.network.pages["/calculators/dilution"] =
      '<script src="/_next/static/chunks/calc.js"></script>';
    await sw.send("message", {
      type: "PRECACHE",
      urls: ["/calculators/dilution", "/account", "https://evil.test/", "no-slash", 5],
    });
    expect(sw.fetched).toContain("/calculators/dilution");
    expect(sw.fetched).toContain("/_next/static/chunks/calc.js");
    expect(sw.fetched).not.toContain("/account");
    expect(sw.fetched.some((p) => p.includes("evil"))).toBe(false);
    sw.network.online = false;
    const res = await sw.request("/calculators/dilution");
    expect(await res!.text()).toContain("calc.js");
  });

  it("waits for a slow network when nothing is saved (slow is not offline)", async () => {
    sw.network.delay = 200; // longer than the 50 ms test timeout
    sw.network.pages["/species/cat"] = "slow but real page";
    const res = await sw.request("/species/cat");
    expect(await res!.text()).toBe("slow but real page");
  });

  it("serves the saved copy when the network is slow, and refreshes it afterwards", async () => {
    sw.network.pages["/drugs/x"] = "old copy";
    await (await sw.request("/drugs/x"))!.text(); // saved
    sw.network.pages["/drugs/x"] = "new copy";
    sw.network.delay = 200;
    const started = Date.now();
    const res = await sw.request("/drugs/x");
    expect(await res!.text()).toBe("old copy");
    expect(Date.now() - started).toBeLessThan(150); // did not wait for the network
    await new Promise((r) => setTimeout(r, 300)); // the late response refreshes the cache
    sw.network.online = false;
    expect(await (await sw.request("/drugs/x"))!.text()).toBe("new copy");
  });

  it("prefers the saved copy over a 5xx from the server", async () => {
    sw.network.pages["/drugs/y"] = "good copy";
    await (await sw.request("/drugs/y"))!.text(); // saved
    sw.network.status = 503;
    sw.network.pages["/drugs/y"] = "Service Unavailable";
    expect(await (await sw.request("/drugs/y"))!.text()).toBe("good copy");
  });

  it("shows the server error when nothing is saved, and never saves error pages", async () => {
    sw.network.status = 502;
    sw.network.pages["/species/horse"] = "Bad gateway";
    const res = await sw.request("/species/horse");
    expect(res!.status).toBe(502);
    sw.network.status = 200;
    sw.network.online = false;
    const later = await sw.request("/species/horse");
    expect(await later!.text()).toBe("cached /offline"); // the error page was not cached
  });

  it("ignores malformed messages", async () => {
    await sw.send("message", { type: "OTHER" });
    await sw.send("message", undefined);
    await sw.send("message", { type: "PRECACHE", urls: "nope" });
  });
});
