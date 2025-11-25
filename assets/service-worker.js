/* Simple runtime caching for previously fetched assets.
 * This enables basic offline use after first load.
 */

const CACHE_NAME = "appfinanzas-runtime-v1";

self.addEventListener("install", (event) => {
  // Optionally pre-cache minimal assets; keeping it light to avoid 404s.
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      try {
        await cache.addAll([
          "/", // initial shell, if accessible
          "/assets/manifest.webmanifest",
        ]);
      } catch (e) {
        // Ignore failures for optional resources.
        console.debug("SW install: some assets not cached", e);
      }
    })()
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
      self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  // Ignore non-GET and cross-origin requests.
  if (request.method !== "GET" || new URL(request.url).origin !== self.location.origin) {
    return;
  }

  event.respondWith(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      try {
        const networkResponse = await fetch(request);
        // Cache a clone of the successful response for offline later.
        cache.put(request, networkResponse.clone());
        return networkResponse;
      } catch (e) {
        // Network failed: try cache.
        const cached = await cache.match(request);
        if (cached) return cached;
        // Optional: return a generic fallback if needed.
        return new Response("Offline", { status: 503, statusText: "Offline" });
      }
    })()
  );
});

