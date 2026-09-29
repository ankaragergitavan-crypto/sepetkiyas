/* SepetKıyas service worker — network-first shell so UI updates appear */
const CACHE = "agt-market-shell-v17";
const SHELL = ["/", "/static/styles.css", "/static/app.js", "/static/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(req)
        .then((res) => res)
        .catch(() =>
          new Response(JSON.stringify({ error: "Çevrimdışı", offline: true }), {
            status: 503,
            headers: { "Content-Type": "application/json" },
          })
        )
    );
    return;
  }

  // HTML/JS/CSS: önce ağ — robot gibi yeni özellikler takılı kalmasın
  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        if (res.ok && url.origin === self.location.origin) {
          caches.open(CACHE).then((cache) => cache.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req))
  );
});
