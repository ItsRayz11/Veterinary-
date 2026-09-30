/* VetRef service worker.
 *
 * Purpose: make public reference pages and the calculators usable offline and repeat visits fast.
 * Never cached: the API (/api/), accounts, admin, exams, the assistant and auth pages, so private
 * or fast-changing data is always fetched fresh from the network.
 */
const VERSION = "v1";
const STATIC_CACHE = `vetref-static-${VERSION}`;
const PAGE_CACHE = `vetref-pages-${VERSION}`;
const OFFLINE_URL = "/offline";
const MAX_PAGES = 60;
const NAV_TIMEOUT_MS = 4000;

// Public, read-only content that is safe to keep for offline use.
const CACHEABLE_PAGES = [
  /^\/$/,
  /^\/calculators(\/|$)/,
  /^\/drugs\//,
  /^\/products\//,
  /^\/companies\//,
  /^\/species(\/|$)/,
  /^\/classes(\/|$)/,
  /^\/countries(\/|$)/,
  /^\/interactions$/,
  /^\/study\/(lessons|books)(\/|$)/,
  /^\/offline$/,
];
const NEVER_CACHE = [
  /^\/api\//,
  /^\/admin/,
  /^\/account/,
  /^\/login/,
  /^\/register/,
  /^\/ask/,
  /^\/study\/exams\//,
  /^\/study\/flashcards/,
  /^\/(jobs|scholarships)\/new/,
];

const allowedPage = (path) =>
  !NEVER_CACHE.some((r) => r.test(path)) && CACHEABLE_PAGES.some((r) => r.test(path));

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(PAGE_CACHE)
      .then((c) => c.add(OFFLINE_URL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith("vetref-") && ![STATIC_CACHE, PAGE_CACHE].includes(k))
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

async function trimPages() {
  const cache = await caches.open(PAGE_CACHE);
  const keys = await cache.keys();
  for (const k of keys.slice(0, Math.max(0, keys.length - MAX_PAGES))) {
    if (!k.url.endsWith(OFFLINE_URL)) await cache.delete(k);
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(STATIC_CACHE);
  const hit = await cache.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok) cache.put(request, res.clone());
  return res;
}

function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error("timeout")), ms);
    promise.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (e) => {
        clearTimeout(t);
        reject(e);
      },
    );
  });
}

async function networkFirstPage(request) {
  const url = new URL(request.url);
  const cache = await caches.open(PAGE_CACHE);
  const cached = await cache.match(request);
  // Always try the network; a good response refreshes the saved copy even when it arrives late.
  const network = fetch(request).then((res) => {
    if (res.ok && res.type === "basic" && allowedPage(url.pathname)) {
      cache.put(request, res.clone());
      trimPages();
    }
    return res;
  });
  network.catch(() => {}); // a late failure after we already answered must not be unhandled
  try {
    // With a saved copy, do not keep the user waiting on a slow network. With none, wait for the
    // network exactly as the browser would: a slow connection is not the same as being offline.
    return cached ? await withTimeout(network, NAV_TIMEOUT_MS) : await network;
  } catch {
    return cached || (await cache.match(OFFLINE_URL)) || Response.error();
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (NEVER_CACHE.some((r) => r.test(url.pathname))) return;

  if (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(cacheFirst(request));
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(networkFirstPage(request));
  }
});

// The page tells us which public URLs (the calculators) to keep ready for offline use.
self.addEventListener("message", (event) => {
  if (!event.data || event.data.type !== "PRECACHE" || !Array.isArray(event.data.urls)) return;
  event.waitUntil(
    (async () => {
      const pages = await caches.open(PAGE_CACHE);
      const assets = await caches.open(STATIC_CACHE);
      for (const path of event.data.urls) {
        if (typeof path !== "string" || !path.startsWith("/") || !allowedPage(path)) continue;
        try {
          const res = await fetch(path, { credentials: "same-origin" });
          if (!res.ok) continue;
          const html = await res.clone().text();
          await pages.put(path, res);
          const chunks = new Set(html.match(/\/_next\/static\/[^"'\s)\\]+/g) || []);
          await Promise.all(
            [...chunks].map(async (asset) => {
              if (await assets.match(asset)) return;
              const r = await fetch(asset);
              if (r.ok) await assets.put(asset, r);
            }),
          );
        } catch {
          /* offline or blocked: skip, it will be cached on a normal visit */
        }
      }
    })(),
  );
});
