/**
 * Eilatush — Service Worker
 *
 * Strategy:
 *   • Pre-cache the app shell so the PWA opens instantly after first visit
 *   • Cache-first for static assets (icons, fonts, images)
 *   • Stale-while-revalidate for API responses (so the user always sees
 *     yesterday's data immediately, while a fresh fetch happens in the
 *     background and updates the cache for next time)
 *   • Network-first for navigation requests with offline fallback
 *
 * Versioning:
 *   Bump CACHE_VERSION to force-invalidate all caches on the next visit.
 *   This is automatically done on every web deploy (see web-build script).
 */

const CACHE_VERSION = "eilatush-v10-copy-tweak-2026-06-09";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;
const IMAGE_CACHE = `${CACHE_VERSION}-img`;

// Files we want available immediately on every cold load.
const APP_SHELL = [
  "/",
  "/manifest.webmanifest",
  "/icon-192.png",
  "/icon-512.png",
  "/apple-touch-icon.png",
  "/favicon-32.png",
  "/og-image.jpg",
];

// ---------------------------------------------------------------------------
// Install — pre-cache the app shell
// ---------------------------------------------------------------------------
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      // Use addAll but ignore failures (some paths may not exist in dev)
      return Promise.all(
        APP_SHELL.map((url) =>
          cache.add(url).catch((err) => {
            console.warn("[SW] failed to precache", url, err);
          })
        )
      );
    })
  );
  // Activate immediately, don't wait for old tabs to close
  self.skipWaiting();
});

// ---------------------------------------------------------------------------
// Activate — purge old caches from previous deploys
// ---------------------------------------------------------------------------
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => !k.startsWith(CACHE_VERSION))
          .map((k) => caches.delete(k))
      )
    )
  );
  // Take control of open clients without requiring a reload
  self.clients.claim();
});

// ---------------------------------------------------------------------------
// Fetch — routing
// ---------------------------------------------------------------------------
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Backend API → stale-while-revalidate
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(staleWhileRevalidate(req, API_CACHE));
    return;
  }

  // Images → cache-first
  if (req.destination === "image" || /\.(png|jpg|jpeg|gif|webp|svg|ico)$/i.test(url.pathname)) {
    event.respondWith(cacheFirst(req, IMAGE_CACHE));
    return;
  }

  // Static assets (JS / CSS / fonts) → stale-while-revalidate
  // (serve cached for instant load, but always fetch fresh in the background so
  //  the next visit has the latest bundle)
  if (
    req.destination === "script" ||
    req.destination === "style" ||
    req.destination === "font" ||
    /\.(js|css|woff2?|ttf|otf)$/i.test(url.pathname)
  ) {
    event.respondWith(staleWhileRevalidate(req, STATIC_CACHE));
    return;
  }

  // Page navigations → network-first with cache fallback
  if (req.mode === "navigate") {
    event.respondWith(networkFirst(req, STATIC_CACHE));
    return;
  }
});

// ---------------------------------------------------------------------------
// Strategies
// ---------------------------------------------------------------------------
async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const fresh = await fetch(request);
    if (fresh && fresh.status === 200) cache.put(request, fresh.clone());
    return fresh;
  } catch (err) {
    return cached || new Response("", { status: 504, statusText: "Offline" });
  }
}

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const fresh = await fetch(request);
    if (fresh && fresh.status === 200) cache.put(request, fresh.clone());
    return fresh;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    // Last-resort offline page
    return cache.match("/") || new Response("offline", { status: 503 });
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const fetchPromise = fetch(request)
    .then((response) => {
      if (response && response.status === 200) cache.put(request, response.clone());
      return response;
    })
    .catch(() => null);
  return cached || (await fetchPromise) || new Response("", { status: 504 });
}

// ---------------------------------------------------------------------------
// Allow the page to force-update the SW (used after a new deploy)
// ---------------------------------------------------------------------------
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
