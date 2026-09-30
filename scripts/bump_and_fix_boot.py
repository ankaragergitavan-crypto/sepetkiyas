from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- Quiet boot script in index.html ---
idx_path = ROOT / "frontend" / "index.html"
t = idx_path.read_text(encoding="utf-8")

# bump 23/24 -> 25 for cache bust
for old in ("23", "24"):
    t = t.replace(f"v={old}", "v=25")
    t = t.replace(f'"{old}"', '"25"')

marker_candidates = [
    '    <script src="/static/app.js?v=25" defer></script>',
    '    <script src="/static/app.js?v=24" defer></script>',
    '    <script src="/static/app.js?v=23" defer></script>',
]
idx = -1
for m in marker_candidates:
    idx = t.find(m)
    if idx >= 0:
        break
if idx < 0:
    # already multi-line script tag?
    idx = t.find('<script src="/static/app.js')
assert idx >= 0, "app.js script tag not found"

end = t.rfind("</body>")
assert end > idx

new_tail = """    <script src="/static/app.js?v=25" defer
      onload="window.__AGT_JS_OK=1"
      onerror="window.__AGT_JS_OK=0"></script>
    <script>
      (function () {
        function hideBanner() {
          var b = document.getElementById("bootBanner");
          if (!b) return;
          b.hidden = true;
          b.textContent = "";
          b.className = "boot-banner";
        }
        function showConnecting() {
          if (window.__AGT_READY || window.__AGT_JS_OK === 1) return;
          var b = document.getElementById("bootBanner");
          if (!b) return;
          b.hidden = false;
          b.className = "boot-banner";
          b.textContent = "Bağlanıyor…";
        }
        function showReloadOnce() {
          if (window.__AGT_READY || window.__AGT_JS_OK === 1 || (window.AGT && window.AGT.search)) return;
          var b = document.getElementById("bootBanner");
          if (!b) return;
          b.hidden = false;
          b.className = "boot-banner err";
          b.innerHTML =
            'Uygulama yüklenemedi. <button type="button" id="bootReloadBtn" class="ghost-btn tiny-btn">Yenile</button>';
          var btn = document.getElementById("bootReloadBtn");
          if (btn) {
            btn.onclick = function () {
              try { localStorage.removeItem("agt_build"); } catch (e) {}
              location.reload();
            };
          }
        }
        var slow = setTimeout(showConnecting, 3000);
        fetch("/api/health", { cache: "no-store", credentials: "same-origin" })
          .then(function () { clearTimeout(slow); if (!window.__AGT_READY) hideBanner(); })
          .catch(function () { clearTimeout(slow); });
        setTimeout(function () {
          if (window.__AGT_READY || window.__AGT_JS_OK === 1 || (window.AGT && window.AGT.search)) {
            hideBanner();
            return;
          }
          showReloadOnce();
        }, 12000);
      })();
    </script>
  </body>
</html>
"""

head = t[:idx]
# ensure head versions are 25
for old in ("23", "24"):
    head = head.replace(f"v={old}", "v=25").replace(f'"{old}"', '"25"')
idx_path.write_text(head + new_tail, encoding="utf-8")
print("index ok", "geç yüklendi" not in idx_path.read_text(encoding="utf-8"))

# --- bump other files ---
replacements = {
    ROOT / "frontend" / "app.js": [
        ('build: "23"', 'build: "25"'),
        ('build: "24"', 'build: "25"'),
        ("/sw.js?v=23", "/sw.js?v=25"),
        ("/sw.js?v=24", "/sw.js?v=25"),
    ],
    ROOT / "frontend" / "manifest.webmanifest": [
        ("v=23", "v=25"),
        ("v=24", "v=25"),
    ],
    ROOT / "backend" / "build_info.py": [
        ('"23"', '"25"'),
        ('"24"', '"25"'),
    ],
    ROOT / "render.yaml": [
        ('value: "23"', 'value: "25"'),
        ('value: "24"', 'value: "25"'),
    ],
}
for path, pairs in replacements.items():
    txt = path.read_text(encoding="utf-8")
    for a, b in pairs:
        txt = txt.replace(a, b)
    path.write_text(txt, encoding="utf-8")
    print(path.name, "bumped")

# --- sw.js shell cache v25 ---
sw = ROOT / "frontend" / "sw.js"
sw.write_text(
    """/* AGT MARKET PWA — kabuk önbellekte; deploy sonrası otomatik güncellenir */
const BUILD = "25";
const CACHE = "agt-market-shell-v25";

const SHELL = [
  "/",
  "/static/app.js?v=25",
  "/static/styles.css?v=25",
  "/manifest.webmanifest?v=25",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/apple-touch-icon.png",
  "/static/icons/icon-maskable-512.png",
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      Promise.all(SHELL.map((url) => cache.add(url).catch(() => undefined)))
    )
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  const data = event.data;
  if (data === "SKIP_WAITING" || (data && data.type === "SKIP_WAITING")) {
    self.skipWaiting();
  }
});

function isShellPath(pathname) {
  return (
    pathname === "/" ||
    pathname.endsWith(".html") ||
    pathname.endsWith(".js") ||
    pathname.endsWith(".css") ||
    pathname === "/sw.js" ||
    pathname.endsWith("manifest.webmanifest") ||
    pathname.startsWith("/static/icons/")
  );
}

async function staleWhileRevalidate(req) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(req);
  const network = fetch(req, { cache: "no-store" })
    .then((res) => {
      if (res && res.ok) {
        cache.put(req, res.clone()).catch(() => {});
      }
      return res;
    })
    .catch(() => cached);
  if (cached) {
    network.catch(() => {});
    return cached;
  }
  return network;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  let url;
  try {
    url = new URL(req.url);
  } catch {
    return;
  }
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(req, { cache: "no-store" }).catch(
        () =>
          new Response(
            JSON.stringify({
              error: "Çevrimdışı veya sunucu uyanıyor",
              offline: true,
            }),
            { status: 503, headers: { "Content-Type": "application/json" } }
          )
      )
    );
    return;
  }

  if (isShellPath(url.pathname)) {
    event.respondWith(staleWhileRevalidate(req));
    return;
  }

  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((cache) => cache.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req))
  );
});
""",
    encoding="utf-8",
)
print("sw.js ok")
