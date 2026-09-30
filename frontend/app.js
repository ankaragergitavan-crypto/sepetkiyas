// Erken işaret — HTML kurtarma betiği “geç yüklendi” sanmasın
window.__AGT_READY = false;
window.AGT = window.AGT || { build: "30" };

const state = {
  markets: [],
  cities: [],
  offers: [],
  groups: [],
  volumeOptions: [],
  activeVolume: "all",
  viewMode: "grouped",
  carts: loadCarts(),
  missingItems: [],
  deferredPrompt: null,
};

const els = {
  form: document.getElementById("searchForm"),
  query: document.getElementById("query"),
  city: document.getElementById("city"),
  searchBtn: document.getElementById("searchBtn"),
  chips: document.getElementById("marketChips"),
  resultsSection: document.getElementById("resultsSection"),
  emptyState: document.getElementById("emptyState"),
  resultsTitle: document.getElementById("resultsTitle"),
  resultsMeta: document.getElementById("resultsMeta"),
  statusRow: document.getElementById("statusRow"),
  robotCard: document.getElementById("robotCard"),
  volumeRow: document.getElementById("volumeRow"),
  offerList: document.getElementById("offerList"),
  cartToggle: document.getElementById("cartToggle"),
  cartBadge: document.getElementById("cartBadge"),
  tabCartBadge: document.getElementById("tabCartBadge"),
  cartDrawer: document.getElementById("cartDrawer"),
  closeCart: document.getElementById("closeCart"),
  scrim: document.getElementById("scrim"),
  cartPanels: document.getElementById("cartPanels"),
  cartWinner: document.getElementById("cartWinner"),
  cartGroupTotals: document.getElementById("cartGroupTotals"),
  grandTotal: document.getElementById("grandTotal"),
  viewToggle: document.getElementById("viewToggle"),
  clearCarts: document.getElementById("clearCarts"),
  downloadCartPdf: document.getElementById("downloadCartPdf"),
  pdfMsg: document.getElementById("pdfMsg"),
  scanCameraBtn: document.getElementById("scanCameraBtn"),
  scanGalleryBtn: document.getElementById("scanGalleryBtn"),
  scanLiveBtn: document.getElementById("scanLiveBtn"),
  scanFileInput: document.getElementById("scanFileInput"),
  scanGalleryInput: document.getElementById("scanGalleryInput"),
  scanStatus: document.getElementById("scanStatus"),
  scanModal: document.getElementById("scanModal"),
  closeScanModal: document.getElementById("closeScanModal"),
  scanLiveStatus: document.getElementById("scanLiveStatus"),
  listText: document.getElementById("listText"),
  listScanBtn: document.getElementById("listScanBtn"),
  listPasteBtn: document.getElementById("listPasteBtn"),
  listCameraBtn: document.getElementById("listCameraBtn"),
  listGalleryBtn: document.getElementById("listGalleryBtn"),
  listFileInput: document.getElementById("listFileInput"),
  listGalleryInput: document.getElementById("listGalleryInput"),
  listScanStatus: document.getElementById("listScanStatus"),
  missingSection: document.getElementById("missingSection"),
  missingList: document.getElementById("missingList"),
  installHint: document.getElementById("installHint"),
  installBtn: document.getElementById("installBtn"),
  installHintText: document.getElementById("installHintText"),
  geoBtn: document.getElementById("geoBtn"),
  desktopBtn: document.getElementById("desktopBtn"),
  desktopMsg: document.getElementById("desktopMsg"),
  tabCart: document.getElementById("tabCart"),
  liveTimer: document.getElementById("liveTimer"),
  liveTimerValue: document.getElementById("liveTimerValue"),
  quickQueries: document.getElementById("quickQueries"),
  productModal: document.getElementById("productModal"),
  productModalBody: document.getElementById("productModalBody"),
  productModalTitle: document.getElementById("productModalTitle"),
  closeProductModal: document.getElementById("closeProductModal"),
};

async function syncTimer() {
  try {
    const res = await apiFetch("/api/timer", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    const hrs = Math.round(data.freeHoursPerMonth ?? 750);
    if (els.liveTimerValue) els.liveTimerValue.textContent = `${hrs} saat`;
    els.liveTimer?.setAttribute(
      "title",
      data.note || `Ücretsiz kota: ayda ${hrs} saat. Her ayın 1'inde yenilenir.`
    );
  } catch {
    /* ignore */
  }
}

function startTimerLoop() {
  syncTimer();
}

function loadCarts() {
  try {
    return JSON.parse(localStorage.getItem("sepetkiyas.carts") || "{}");
  } catch {
    return {};
  }
}

function saveCarts() {
  localStorage.setItem("sepetkiyas.carts", JSON.stringify(state.carts));
}

function money(n) {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
  }).format(n || 0);
}

async function apiFetch(url, options = {}) {
  const opts = {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
    headers: {
      ...(options.headers || {}),
    },
  };
  const res = await fetch(url, opts);
  if (res.status === 401 || res.status === 403) {
    const data = await res.clone().json().catch(() => ({}));
    if (data.code === "auth_required" || res.status === 401) {
      showGate(true, data.detail || "Giriş gerekli");
    }
    if (data.code === "ip_blocked") {
      showGate(true, "IP güvenlik duvarı: erişim engellendi");
    }
  }
  return res;
}

function showGate(show, msg) {
  const overlay = document.getElementById("gateOverlay");
  const gateMsg = document.getElementById("gateMsg");
  if (!overlay) return;
  overlay.hidden = !show;
  if (gateMsg && msg) gateMsg.textContent = msg;
}

async function checkGate() {
  try {
    const res = await apiFetch("/api/auth/status");
    const data = await res.json();
    if (data.gateEnabled && !data.unlocked) {
      showGate(true, data.hint || "Erişim şifresi gerekli");
      return false;
    }
    showGate(false);
    return true;
  } catch {
    return true;
  }
}

async function unlockGate() {
  const pinEl = document.getElementById("gatePin");
  const gateMsg = document.getElementById("gateMsg");
  const pin = (pinEl?.value || "").trim();
  if (!pin) {
    if (gateMsg) gateMsg.textContent = "Şifre girin";
    return;
  }
  try {
    const res = await apiFetch("/api/auth/unlock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Şifre hatalı");
    showGate(false);
    if (gateMsg) gateMsg.textContent = "";
    // Tam boot için yenile (cookie set edildi)
    location.reload();
  } catch (err) {
    if (gateMsg) gateMsg.textContent = err.message || "Şifre hatalı";
  }
}

function unitPriceLabel(o) {
  if (o.unitPriceEstimate == null) return o.unitPrice || "";
  const unit = o.unitPriceUnit || "kg";
  return `≈ ${Number(o.unitPriceEstimate).toFixed(0)} ₺/${unit}`;
}

function lowestPrice(offers) {
  const prices = (offers || [])
    .map((o) => Number(o.price))
    .filter((p) => Number.isFinite(p) && p > 0);
  return prices.length ? Math.min(...prices) : null;
}

function isBestPrice(o, best) {
  return best != null && Number(o.price) === best;
}

function cartCount() {
  return Object.values(state.carts).reduce(
    (sum, items) => sum + items.reduce((s, i) => s + i.qty, 0),
    0
  );
}

function cartGrandTotal() {
  return Object.values(state.carts).reduce(
    (sum, items) => sum + items.reduce((s, i) => s + i.price * i.qty, 0),
    0
  );
}

function selectedCity() {
  const fallback = { id: "ankara-cankaya", label: "Ankara · Çankaya", lat: 39.9208, lon: 32.8541 };
  const presets = state.cities?.length
    ? state.cities
    : [
        { id: "ankara-kecioren", label: "Ankara · Keçiören", lat: 39.9777, lon: 32.867 },
        { id: "ankara-cankaya", label: "Ankara · Çankaya", lat: 39.9208, lon: 32.8541 },
        { id: "ankara-yenimahalle", label: "Ankara · Yenimahalle", lat: 39.9667, lon: 32.8111 },
        { id: "ankara-mamak", label: "Ankara · Mamak", lat: 39.92, lon: 32.91 },
        { id: "ankara-etimesgut", label: "Ankara · Etimesgut", lat: 39.95, lon: 32.67 },
        { id: "ankara-sincan", label: "Ankara · Sincan", lat: 39.966, lon: 32.58 },
        { id: "ankara-pursaklar", label: "Ankara · Pursaklar", lat: 40.04, lon: 32.9 },
      ];
  const id = els.city?.value;
  const fromState = presets.find((c) => c.id === id);
  if (fromState) return fromState;
  // HTML option data-lat/lon yedek
  const opt = els.city?.selectedOptions?.[0];
  if (opt?.dataset?.lat && opt?.dataset?.lon) {
    return {
      id: opt.value,
      label: opt.textContent.trim(),
      lat: Number(opt.dataset.lat),
      lon: Number(opt.dataset.lon),
    };
  }
  return presets[0] || fallback;
}

function cityDistanceKm(lat1, lon1, lat2, lon2) {
  const r = 6371;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dphi = ((lat2 - lat1) * Math.PI) / 180;
  const dlmb = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dphi / 2) ** 2 +
    Math.cos(p1) * Math.cos(p2) * Math.sin(dlmb / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}

function pickCityByCoords(lat, lon) {
  const list = state.cities?.length
    ? state.cities
    : [
        { id: "ankara-kecioren", label: "Ankara · Keçiören", lat: 39.9777, lon: 32.867 },
        { id: "ankara-cankaya", label: "Ankara · Çankaya", lat: 39.9208, lon: 32.8541 },
        { id: "ankara-yenimahalle", label: "Ankara · Yenimahalle", lat: 39.9667, lon: 32.8111 },
        { id: "ankara-mamak", label: "Ankara · Mamak", lat: 39.92, lon: 32.91 },
        { id: "ankara-etimesgut", label: "Ankara · Etimesgut", lat: 39.95, lon: 32.67 },
        { id: "ankara-sincan", label: "Ankara · Sincan", lat: 39.966, lon: 32.58 },
        { id: "ankara-pursaklar", label: "Ankara · Pursaklar", lat: 40.04, lon: 32.9 },
      ];
  let best = null;
  let bestD = Infinity;
  for (const c of list) {
    const d = cityDistanceKm(lat, lon, c.lat, c.lon);
    if (d < bestD) {
      bestD = d;
      best = c;
    }
  }
  // Ankara metropol dışıysa seçme
  if (!best || bestD > 45) return null;
  return best;
}

function saveSelectedCity(cityId) {
  const id = String(cityId || "").trim();
  if (!id) return;
  try {
    localStorage.setItem("agt_city", id);
  } catch {
    /* ignore */
  }
}

function loadSavedCityId() {
  try {
    return localStorage.getItem("agt_city");
  } catch {
    return null;
  }
}

function applyCitySelection(city, note, { persist = true, emitChange = true } = {}) {
  if (!city || !els.city) return false;
  const exists = [...els.city.options].some((o) => o.value === city.id);
  if (!exists) return false;
  els.city.value = city.id;
  if (persist) saveSelectedCity(city.id);
  if (emitChange) els.city.dispatchEvent(new Event("change", { bubbles: true }));
  if (note) setScanStatus(note, false);
  return true;
}

function autoSelectByGeolocation(interactive = false) {
  if (!navigator.geolocation) {
    if (interactive) setScanStatus("Bu cihazda konum API’si yok.", false);
    return;
  }
  if (interactive) setScanStatus("Konum alınıyor…", false);
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const city = pickCityByCoords(pos.coords.latitude, pos.coords.longitude);
      if (city) {
        applyCitySelection(city, `Konum algılandı: ${city.label}`, {
          persist: true,
          emitChange: true,
        });
      } else if (interactive) {
        setScanStatus("Konum Ankara dışında — ilçeyi elle seçin.", false);
      }
    },
    (err) => {
      if (interactive) {
        setScanStatus(
          err?.code === 1
            ? "Konum izni kapalı. Ayarlardan konum açın veya ilçeyi elle seçin."
            : "Konum alınamadı — ilçeyi elle seçin.",
          false
        );
      }
    },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 120000 }
  );
}

function dismissKeyboard() {
  const q = els.query;
  if (!q) return;
  try {
    q.blur();
    if (document.activeElement && document.activeElement !== document.body) {
      document.activeElement.blur();
    }
  } catch {
    /* ignore */
  }
}

function registerPwa() {
  if (!("serviceWorker" in navigator)) return;

  const bumpSw = (reg) => {
    if (!reg) return;
    reg.update().catch(() => {});
    if (reg.waiting) reg.waiting.postMessage("SKIP_WAITING");
  };

  navigator.serviceWorker
    .register("/sw.js?v=30")
    .then((reg) => {
      bumpSw(reg);
      reg.addEventListener("updatefound", () => {
        const sw = reg.installing;
        if (!sw) return;
        sw.addEventListener("statechange", () => {
          if (sw.state === "installed") {
            sw.postMessage("SKIP_WAITING");
          }
        });
      });
      // Periyodik güncelleme — Manual Deploy sonrası yüklü telefonlar
      setInterval(() => bumpSw(reg), 45000);
    })
    .catch(() => {});

  let refreshing = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (refreshing) return;
    refreshing = true;
    location.reload();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    navigator.serviceWorker.getRegistration().then(bumpSw).catch(() => {});
    ensureLatestFromServer();
  });

  window.addEventListener("focus", () => {
    navigator.serviceWorker.getRegistration().then(bumpSw).catch(() => {});
    ensureLatestFromServer();
  });

  ensureLatestFromServer();
  setInterval(ensureLatestFromServer, 60000);
}

async function ensureLatestFromServer() {
  try {
    const res = await fetch("/api/version", { cache: "no-store", credentials: "same-origin" });
    if (!res.ok) return;
    const data = await res.json();
    const remote = String(data.build || "");
    if (!remote) return;
    const local = String(window.__AGT_BUILD || "");
    const stored = localStorage.getItem("agt_build");
    localStorage.setItem("agt_build", remote);
    if (remote === local && (!stored || stored === remote)) return;

    const regs = await navigator.serviceWorker.getRegistrations();
    await Promise.all(
      regs.map(async (r) => {
        await r.update().catch(() => {});
        if (r.waiting) r.waiting.postMessage("SKIP_WAITING");
      })
    );
    if (caches?.keys) {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    }
    if (sessionStorage.getItem("agt_reloaded_" + remote) === "1") return;
    sessionStorage.setItem("agt_reloaded_" + remote, "1");
    const u = new URL(location.href);
    u.searchParams.set("v", remote);
    location.replace(u.toString());
  } catch {
    /* ignore */
  }
}

function hideBootBanner() {
  const banner = document.getElementById("bootBanner");
  if (!banner) return;
  banner.hidden = true;
  banner.textContent = "";
  banner.className = "boot-banner";
}

async function wakeServer() {
  const banner = document.getElementById("bootBanner");
  let slowTimer = null;
  try {
    // Hemen uyarı yok — yalnızca gerçekten yavaşsa “Bağlanıyor…”
    slowTimer = setTimeout(() => {
      if (!banner || window.__AGT_READY) return;
      banner.hidden = false;
      banner.className = "boot-banner";
      banner.textContent = "Bağlanıyor…";
    }, 2800);
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 60000);
    const res = await apiFetch("/api/health", { cache: "no-store", signal: ctrl.signal });
    clearTimeout(t);
    clearTimeout(slowTimer);
    if (!res.ok) throw new Error("health");
    hideBootBanner();
    return true;
  } catch {
    clearTimeout(slowTimer);
    if (banner) {
      banner.hidden = false;
      banner.className = "boot-banner err";
      banner.innerHTML =
        'Bağlantı yok. İnterneti kontrol edin. <button type="button" id="bootReloadBtn" class="ghost-btn tiny-btn">Yenile</button>';
      document.getElementById("bootReloadBtn")?.addEventListener("click", () => {
        location.reload();
      });
    }
    return false;
  }
}

function setupInstall() {
  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const isAndroid = /android/i.test(navigator.userAgent);
  const isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;

  if (els.installHint) els.installHint.hidden = !!isStandalone;
  if (isStandalone) return;

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    state.deferredPrompt = e;
    if (els.installHint) els.installHint.hidden = false;
    if (els.installHintText) {
      els.installHintText.textContent = "Hazır — Telefona yükle’ye basın";
    }
  });

  els.installBtn?.addEventListener("click", async () => {
    if (state.deferredPrompt) {
      try {
        state.deferredPrompt.prompt();
        await state.deferredPrompt.userChoice;
      } catch {
        /* ignore */
      }
      state.deferredPrompt = null;
      if (els.installHintText) {
        els.installHintText.textContent = "Yükleme penceresi açıldı / tamamlandı";
      }
      return;
    }
    if (isIos) {
      alert(
        "iPhone/iPad: Safari’de alttaki Paylaş (kare+ok) → “Ana Ekrana Ekle” → Ekle.\n\nAGT MARKET KARŞILAŞTIRMA ana ekranınıza gelir."
      );
      return;
    }
    if (isAndroid) {
      alert(
        "Android Chrome: sağ üst ⋮ menü → “Ana ekrana ekle” veya “Uygulamayı yükle”.\n\nMenüde yoksa bu sayfayı Chrome ile açıp tekrar deneyin."
      );
      return;
    }
    alert(
      "Tarayıcı menüsünden “Uygulamayı yükle / Ana ekrana ekle” seçin.\nWindows’ta Chrome adres çubuğundaki bilgisayar+ikonuna da basabilirsiniz."
    );
  });
}

async function boot() {
  fitViewportToScreen();
  window.addEventListener("resize", fitViewportToScreen);
  window.visualViewport?.addEventListener("resize", fitViewportToScreen);
  window.visualViewport?.addEventListener("scroll", fitViewportToScreen);

  document.getElementById("gateUnlockBtn")?.addEventListener("click", () => unlockGate());
  document.getElementById("gatePin")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") unlockGate();
  });

  const open = await checkGate();
  if (!open) {
    // Kilit açık değilse sunucu çağrılarını bekle
    registerPwa();
    return;
  }

  registerPwa();
  setupInstall();
  startTimerLoop();
  await wakeServer();

  if (new URLSearchParams(location.search).get("focus") === "search") {
    // Odaklama yok — sadece üst arama paneli görünsün
    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  }

  try {
    const res = await apiFetch("/api/markets");
    const data = await res.json();
    state.markets = data.markets || [];
    state.cities = data.cities || [];
    if (els.quickQueries) {
      const qs = data.quickQueries || [];
      els.quickQueries.innerHTML = qs
        .map(
          (q) =>
            `<button type="button" class="quick-chip" data-q="${escapeHtml(q)}">${escapeHtml(q)}</button>`
        )
        .join("");
    }
  } catch (err) {
    console.error(err);
    state.markets = state.markets || [];
    state.cities = [
      { id: "ankara-kecioren", label: "Ankara · Keçiören", lat: 39.9777, lon: 32.867 },
      { id: "ankara-cankaya", label: "Ankara · Çankaya", lat: 39.9208, lon: 32.8541 },
      { id: "ankara-yenimahalle", label: "Ankara · Yenimahalle", lat: 39.9667, lon: 32.8111 },
      { id: "ankara-mamak", label: "Ankara · Mamak", lat: 39.92, lon: 32.91 },
      { id: "ankara-etimesgut", label: "Ankara · Etimesgut", lat: 39.95, lon: 32.67 },
      { id: "ankara-sincan", label: "Ankara · Sincan", lat: 39.966, lon: 32.58 },
      { id: "ankara-pursaklar", label: "Ankara · Pursaklar", lat: 40.04, lon: 32.9 },
    ];
  }

  if (els.city && (state.cities || []).length) {
    const saved = loadSavedCityId();
    const prev = saved || els.city.value || "ankara-cankaya";
    els.city.innerHTML = state.cities
      .map(
        (c) =>
          `<option value="${c.id}" data-lat="${c.lat}" data-lon="${c.lon}">${escapeHtml(c.label)}</option>`
      )
      .join("");
    if ([...els.city.options].some((o) => o.value === prev)) {
      els.city.value = prev;
      saveSelectedCity(prev);
    }
  }

  // GPS yalnızca 📍 butonuna basınca — açılışta kaydedilmiş ilçe kalsın
  els.geoBtn?.addEventListener("click", () => autoSelectByGeolocation(true));
  if (els.chips) {
    els.chips.innerHTML = (state.markets || [])
      .map(
        (m) => `
      <span class="chip ${m.live ? "live" : ""}" title="${escapeHtml(m.hint || "")}">
        <span class="dot" style="background:${m.color}"></span>
        ${m.label}
        <span class="tag">${m.live ? "canlı" : "bekleniyor"}</span>
      </span>`
      )
      .join("");
  }

  renderCarts();
}

function openDrawer(open) {
  if (!els.cartDrawer) return;
  els.cartDrawer.classList.toggle("open", open);
  els.cartDrawer.setAttribute("aria-hidden", String(!open));
  els.cartToggle?.setAttribute("aria-expanded", String(open));
  if (els.scrim) els.scrim.hidden = !open;
  els.tabCart?.classList.toggle("active", open);
}

function addToCart(offer, meta = {}) {
  const key = offer.marketId;
  if (!state.carts[key]) state.carts[key] = [];
  const existing = state.carts[key].find((i) => i.id === offer.id);
  if (existing) existing.qty += 1;
  else {
    state.carts[key].push({
      id: offer.id,
      title: offer.title,
      price: offer.price,
      marketId: offer.marketId,
      marketLabel: offer.marketLabel,
      imageUrl: offer.imageUrl,
      qty: 1,
      listItem: meta.listItem || null,
      matchType: meta.matchType || null,
      similarNote: meta.similarNote || null,
      volume: offer.volume || null,
      brand: offer.brand || null,
    });
  }
  saveCarts();
  renderCarts();
  if (meta.openDrawer !== false) openDrawer(true);
}

function changeQty(marketId, itemId, delta) {
  const list = state.carts[marketId] || [];
  const item = list.find((i) => i.id === itemId);
  if (!item) return;
  item.qty += delta;
  if (item.qty <= 0) {
    state.carts[marketId] = list.filter((i) => i.id !== itemId);
    if (!state.carts[marketId].length) delete state.carts[marketId];
  }
  saveCarts();
  renderCarts();
}

function removeFromCart(marketId, itemId) {
  const list = state.carts[marketId] || [];
  state.carts[marketId] = list.filter((i) => i.id !== itemId);
  if (!state.carts[marketId]?.length) delete state.carts[marketId];
  saveCarts();
  renderCarts();
}

function fitViewportToScreen() {
  const vv = window.visualViewport;
  const h = vv?.height || window.innerHeight || document.documentElement.clientHeight;
  if (h > 0) {
    document.documentElement.style.setProperty("--app-vh", `${Math.round(h)}px`);
  }
  document.documentElement.style.setProperty(
    "--gutter-safe",
    `max(${getComputedStyle(document.documentElement).getPropertyValue("--gutter").trim() || "0.75rem"}, env(safe-area-inset-left), env(safe-area-inset-right))`
  );
  const chrome = document.getElementById("appChrome");
  if (chrome) {
    document.documentElement.style.setProperty("--chrome-h", `${chrome.offsetHeight}px`);
  }
}

function renderCarts() {
  const count = cartCount();
  els.cartBadge.textContent = String(count);
  if (els.tabCartBadge) els.tabCartBadge.textContent = String(count);
  els.grandTotal.textContent = money(cartGrandTotal());

  const marketMap = Object.fromEntries(state.markets.map((m) => [m.id, m]));
  const ids = Object.keys(state.carts);

  if (!ids.length) {
    if (els.cartWinner) {
      els.cartWinner.hidden = true;
      els.cartWinner.innerHTML = "";
    }
    if (els.cartGroupTotals) {
      els.cartGroupTotals.hidden = true;
      els.cartGroupTotals.innerHTML = "";
    }
    if (els.downloadCartPdf) els.downloadCartPdf.disabled = true;
    els.cartPanels.innerHTML =
      '<p class="muted">Henüz ürün yok. Sonuçlardan “Sepete ekle” ile market bazlı sepet doldurun.</p>';
    return;
  }

  if (els.downloadCartPdf) els.downloadCartPdf.disabled = false;

  const totals = ids.map((marketId) => {
    const items = state.carts[marketId];
    const total = items.reduce((s, i) => s + i.price * i.qty, 0);
    const qty = items.reduce((s, i) => s + i.qty, 0);
    return { marketId, total, items, qty };
  });
  totals.sort((a, b) => a.total - b.total);
  const winner = totals[0];
  if (els.cartWinner) {
    const meta = marketMap[winner.marketId];
    els.cartWinner.hidden = false;
    els.cartWinner.innerHTML = `En ucuz sepet grubu: <strong>${escapeHtml(meta?.label || winner.marketId)}</strong> · <strong>${money(winner.total)}</strong>`;
  }

  if (els.cartGroupTotals) {
    els.cartGroupTotals.hidden = false;
    els.cartGroupTotals.innerHTML = `
      <h3 class="cart-groups-title">Market grupları · toplam tutarlar</h3>
      <ul class="cart-groups-list">
        ${totals
          .map(({ marketId, total, qty }, i) => {
            const meta = marketMap[marketId];
            const cheapest = i === 0;
            return `<li class="${cheapest ? "is-cheapest" : ""}">
              <span class="market-badge"><i style="background:${meta?.color || "#999"}"></i>${escapeHtml(meta?.label || marketId)}</span>
              <span class="muted tiny">${qty} ürün${cheapest ? " · en ucuz" : ""}</span>
              <strong class="group-sum">${money(total)}</strong>
            </li>`;
          })
          .join("")}
      </ul>
      <p class="muted tiny cart-groups-note">Her satır o market sepetinin kendi toplamıdır (karşılaştırma).</p>
    `;
  }

  els.cartPanels.innerHTML = totals
    .map(({ marketId, total, items, qty }) => {
      const meta = marketMap[marketId];
      const isWin = marketId === winner.marketId;
      return `
        <section class="cart-panel ${isWin ? "winner" : ""}">
          <h3>
            <span class="market-badge">
              <i style="background:${meta?.color || "#999"}"></i>
              ${escapeHtml(meta?.label || marketId)}${isWin ? " · en ucuz" : ""}
            </span>
            <span>${qty} ürün</span>
          </h3>
          ${items
            .map(
              (item) => `
            <div class="cart-item">
              ${productThumbHtml(item.imageUrl, "product-thumb thumb-sm")}
              <div>
                <div>${escapeHtml(item.title)}</div>
                <div class="muted tiny">${money(item.price)} × ${item.qty}${item.volume ? ` · ${escapeHtml(item.volume)}` : ""}</div>
                ${
                  item.listItem
                    ? `<div class="muted tiny">Liste: ${escapeHtml(item.listItem)}${item.matchType === "similar" ? " · benzer" : " · aynı"}</div>`
                    : ""
                }
                ${item.similarNote ? `<div class="similar-note">${escapeHtml(item.similarNote)}</div>` : ""}
                <div class="cart-item-actions">
                  <div class="qty-row">
                    <button class="qty-btn" data-market="${marketId}" data-id="${escapeHtml(item.id)}" data-delta="-1" aria-label="Azalt">−</button>
                    <span>${item.qty}</span>
                    <button class="qty-btn" data-market="${marketId}" data-id="${escapeHtml(item.id)}" data-delta="1" aria-label="Artır">+</button>
                  </div>
                  <button type="button" class="remove-item-btn" data-market="${marketId}" data-id="${escapeHtml(item.id)}" data-remove="1">Kaldır</button>
                </div>
              </div>
              <div class="line-total">${money(item.price * item.qty)}</div>
            </div>`
            )
            .join("")}
          <div class="panel-total">
            <span>${escapeHtml(meta?.label || marketId)} sepet toplamı</span>
            <strong>${money(total)}</strong>
          </div>
        </section>`;
    })
    .join("");
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

window.__AGT_PLACEHOLDER =
  "data:image/svg+xml," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96"><rect width="96" height="96" rx="14" fill="#0b140f"/><text x="48" y="55" text-anchor="middle" fill="#5cff9a" font-family="Arial,sans-serif" font-size="22" font-weight="800">AGT</text></svg>'
  );

function normalizeImageUrl(url) {
  let u = String(url || "").trim();
  if (!u) return "";
  if (u.startsWith("//")) u = `https:${u}`;
  if (u.startsWith("http://")) u = `https://${u.slice(7)}`;
  return u;
}

function productThumbHtml(url, cls = "product-thumb") {
  const src = normalizeImageUrl(url);
  const ph = window.__AGT_PLACEHOLDER;
  if (!src) {
    return `<img class="${cls} is-placeholder" src="${ph}" alt="" width="72" height="72" decoding="async" />`;
  }
  return `<img class="${cls}" src="${escapeHtml(src)}" alt="" width="72" height="72" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.onerror=null;this.classList.add('is-placeholder');this.src=window.__AGT_PLACEHOLDER" />`;
}

function renderVolumeChips(options) {
  state.volumeOptions = options || [];
  if (!state.volumeOptions.length) {
    els.volumeRow.hidden = true;
    els.volumeRow.innerHTML = "";
    return;
  }
  els.volumeRow.hidden = false;
  const chips = ["all", ...state.volumeOptions];
  els.volumeRow.innerHTML = chips
    .map((v) => {
      const label = v === "all" ? "Tümü" : v;
      const active = state.activeVolume === v ? "active" : "";
      return `<button type="button" class="vol-chip ${active}" data-volume="${escapeHtml(v)}">${escapeHtml(label)}</button>`;
    })
    .join("");
}

function scoreRow(label, score) {
  const s = Math.max(0, Math.min(100, Number(score ?? 50)));
  const hue = Math.round((s / 100) * 120);
  return `
    <div class="score-row">
      <span class="score-label">${label}</span>
      <div class="bar-track"><i style="width:${s}%;background:hsl(${hue} 75% 48%)"></i></div>
      <span class="score-num">${s}%</span>
    </div>`;
}

function findOfferIndex(o) {
  if (!o) return -1;
  const byRef = state.offers.indexOf(o);
  if (byRef >= 0) return byRef;
  return state.offers.findIndex(
    (x) =>
      x.id === o.id ||
      (x.productId &&
        x.productId === o.productId &&
        x.marketId === o.marketId &&
        Number(x.price) === Number(o.price) &&
        (x.depotId || "") === (o.depotId || ""))
  );
}

function offerById(id) {
  if (id == null || id === "") return null;
  return state.offers.find((x) => String(x.id) === String(id)) || null;
}

function offerByIdxOrId(el) {
  if (!el) return null;
  const id = el.dataset.offerId;
  if (id) {
    const found = offerById(id);
    if (found) return found;
  }
  const idx = Number(el.dataset.detailIdx ?? el.dataset.idx);
  if (Number.isFinite(idx) && idx >= 0) return state.offers[idx] || null;
  return null;
}

function openProductModal(open) {
  if (!els.productModal) return;
  els.productModal.hidden = !open;
  els.productModal.setAttribute("aria-hidden", open ? "false" : "true");
  if (!open) els.productModalBody.innerHTML = "";
}

async function showProductContent(offer) {
  if (!offer || !els.productModalBody) return;
  openProductModal(true);
  if (els.productModalTitle) {
    els.productModalTitle.textContent = offer.title || "Ürün içeriği";
  }
  const cats = (offer.categories || []).map((c) => escapeHtml(String(c))).join(", ");
  els.productModalBody.innerHTML = `
    <div class="product-detail-hero">
      ${productThumbHtml(offer.imageUrl, "product-thumb thumb-lg")}
      <div>
        <p class="offer-title">${escapeHtml(offer.title || "")}</p>
        <p class="muted">${escapeHtml([offer.brand, offer.volume].filter(Boolean).join(" · "))}</p>
        <p><strong>${money(offer.price)}</strong> · ${escapeHtml(offer.marketLabel || "")}${
          offer.depotName ? ` · ${escapeHtml(offer.depotName)}` : ""
        }</p>
      </div>
    </div>
    <div class="score-bars" title="${escapeHtml(offer.analysisNote || "Etiket taraması")}">
      ${scoreRow("Sağlık", offer.healthScore)}
      ${scoreRow("Fiyat", offer.economyScore)}
    </div>
    <h3 class="detail-h">Market kaynağı (canlı)</h3>
    <ul class="detail-list">
      ${offer.mainCategory ? `<li>Ana kategori: ${escapeHtml(offer.mainCategory)}</li>` : ""}
      ${offer.menuCategory ? `<li>Menü: ${escapeHtml(offer.menuCategory)}</li>` : ""}
      ${cats ? `<li>Kategoriler: ${cats}</li>` : ""}
      ${offer.promotionText ? `<li>Kampanya: ${escapeHtml(offer.promotionText)}</li>` : ""}
      ${unitPriceLabel(offer) ? `<li>Birim fiyat: ${escapeHtml(unitPriceLabel(offer))}</li>` : ""}
      ${offer.updatedAt ? `<li>Güncelleme: ${escapeHtml(offer.updatedAt)}</li>` : ""}
      <li class="warn-line">İçindekiler listesi market fiyat API’sinde yok.</li>
    </ul>
    <h3 class="detail-h">Etiket analizi</h3>
    <ul class="detail-list">
      ${(offer.labelEvidence || ["nötr sinyal"])
        .map((e) => `<li>${escapeHtml(e)}</li>`)
        .join("")}
    </ul>
    <h3 class="detail-h">İçindekiler (açık veri)</h3>
    <p class="muted" id="offStatus">Open Food Facts aranıyor…</p>
    <div id="offBlock"></div>
    <div class="product-detail-actions">
      <button type="button" class="add-btn" data-idx="${state.offers.indexOf(offer)}">Sepete ekle</button>
    </div>
  `;

  const offStatus = document.getElementById("offStatus");
  const offBlock = document.getElementById("offBlock");
  try {
    const res = await apiFetch("/api/product-content", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: offer.title,
        brand: offer.brand,
        volume: offer.volume,
        categories: offer.categories || [],
        mainCategory: offer.mainCategory,
        menuCategory: offer.menuCategory,
        promotionText: offer.promotionText,
        imageUrl: offer.imageUrl,
        marketLabel: offer.marketLabel,
        depotName: offer.depotName,
        price: offer.price,
        unitPriceEstimate: offer.unitPriceEstimate,
        unitPriceUnit: offer.unitPriceUnit,
        healthScore: offer.healthScore,
        economyScore: offer.economyScore,
        labelEvidence: offer.labelEvidence,
        labelNotes: offer.labelNotes,
        analysisNote: offer.analysisNote,
        source: offer.source,
        updatedAt: offer.updatedAt,
      }),
    });
    const data = await res.json();
    const off = data.openFoodFacts || {};
    if (offStatus) offStatus.textContent = off.note || "";
    if (!offBlock) return;
    if (off.found || off.ingredientsText || off.nutriscore || off.novaGroup) {
      offBlock.innerHTML = `
        <ul class="detail-list">
          ${off.matchedName ? `<li>Eşleşen kayıt: ${escapeHtml(off.matchedName)}${off.matchedBrand ? ` · ${escapeHtml(off.matchedBrand)}` : ""}</li>` : ""}
          ${off.matchScore != null ? `<li>Eşleşme skoru: ${off.matchScore}</li>` : ""}
          ${off.ingredientsText ? `<li class="ingredients"><strong>İçindekiler:</strong> ${escapeHtml(off.ingredientsText)}</li>` : "<li>İçindekiler metni bu kayıtta yok.</li>"}
          ${off.allergens ? `<li>Alerjen: ${escapeHtml(String(off.allergens))}</li>` : ""}
          ${off.nutriscore ? `<li>Nutri-Score: ${escapeHtml(String(off.nutriscore).toUpperCase())}</li>` : ""}
          ${off.novaGroup != null ? `<li>NOVA: ${escapeHtml(String(off.novaGroup))}</li>` : ""}
          ${off.url ? `<li><a href="${escapeHtml(off.url)}" target="_blank" rel="noopener">Open Food Facts kaydı</a></li>` : ""}
        </ul>`;
    } else {
      offBlock.innerHTML = `<p class="muted">${escapeHtml(off.note || "İçindekiler bulunamadı (uydurma eklenmedi).")}</p>`;
    }
  } catch (err) {
    if (offStatus) {
      offStatus.textContent = `İçerik servisi yanıt vermedi: ${err.message || err}`;
    }
  }
}

function trendBadge(o) {
  if (!o.trend || o.trend === "flat") return "";
  const down = o.trend === "down";
  const pct =
    o.priceDeltaPct != null ? ` ${down ? "" : "+"}${o.priceDeltaPct}%` : "";
  const prev = o.prevPrice != null ? ` (önce ${money(o.prevPrice)})` : "";
  return `<span class="trend-badge ${down ? "down" : "up"}" title="Gerçek önceki kayıt${prev}">${
    down ? "↓ düştü" : "↑ yükseldi"
  }${pct}</span>`;
}

function mergeLocalPriceHistory(offers) {
  let hist = {};
  try {
    hist = JSON.parse(localStorage.getItem("sepetkiyas.prices") || "{}");
  } catch {
    hist = {};
  }
  for (const o of offers) {
    const key = `${o.productId || o.id}|${o.depotId || o.marketId || ""}`;
    const prev = hist[key];
    if (!o.trend && prev && typeof prev.price === "number") {
      const delta = Number(o.price) - prev.price;
      if (Math.abs(delta) < 0.005) {
        o.trend = "flat";
        o.priceDelta = 0;
        o.priceDeltaPct = 0;
        o.prevPrice = prev.price;
      } else {
        o.trend = delta > 0 ? "up" : "down";
        o.priceDelta = Math.round(delta * 100) / 100;
        o.priceDeltaPct =
          prev.price !== 0 ? Math.round((delta / prev.price) * 10000) / 100 : null;
        o.prevPrice = prev.price;
      }
    }
    hist[key] = { price: Number(o.price), ts: Date.now() };
  }
  try {
    const keys = Object.keys(hist);
    if (keys.length > 4000) {
      const trimmed = {};
      keys.slice(-3000).forEach((k) => {
        trimmed[k] = hist[k];
      });
      hist = trimmed;
    }
    localStorage.setItem("sepetkiyas.prices", JSON.stringify(hist));
  } catch {
    /* quota */
  }
  return offers;
}

function visibleOffers() {
  let list = state.offers;
  if (state.activeVolume !== "all") {
    const want = state.activeVolume.toUpperCase();
    list = list.filter((o) => {
      const vol = (o.volume || "").toUpperCase().replace("GR", "G");
      const title = (o.title || "").toUpperCase().replace("GR", "G");
      return (
        vol.includes(want) ||
        title.includes(want) ||
        vol.replace(/\s/g, "") === want.replace(/\s/g, "")
      );
    });
  }
  // Yalnız canlı geçerli fiyat (uydurma/0 fiyat yok)
  return list.filter((o) => Number(o.price) > 0);
}

function visibleGroups() {
  const offerIds = new Set(visibleOffers().map((o) => o.id));
  return (state.groups || [])
    .map((g) => ({
      ...g,
      offers: (g.offers || []).filter((o) => offerIds.has(o.id) && Number(o.price) > 0),
    }))
    .filter((g) => g.offers.length);
}

function offerCardHtml(o, idx, bestPrice = null) {
  const realIdx = findOfferIndex(o);
  const offerId = escapeHtml(String(o.id || ""));
  const best = isBestPrice(o, bestPrice);
  const img = productThumbHtml(o.imageUrl);
  const valueBadge = o.valuePick
    ? `<span class="value-badge">Tahmin: uygun fiyat + sade etiket</span>`
    : "";
  const unit = unitPriceLabel(o);
  return `
    <article class="offer ${o.valuePick ? "value-pick" : ""} ${best ? "best-deal" : ""}" data-offer-id="${offerId}" data-detail-idx="${realIdx}" role="button" tabindex="0" style="animation-delay:${Math.min(idx * 0.03, 0.4)}s">
      ${img}
      <div>
        <p class="offer-title">${escapeHtml(o.title)}</p>
        ${valueBadge}
        <div class="offer-meta">
          <span class="market-badge"><i style="background:${o.marketColor}"></i>${escapeHtml(o.marketLabel)}</span>
          ${o.brand ? `<span>${escapeHtml(o.brand)}</span>` : ""}
          ${o.volume ? `<span>${escapeHtml(o.volume)}</span>` : ""}
          ${o.depotName ? `<span>${escapeHtml(o.depotName)}</span>` : ""}
          ${o.distanceKm != null ? `<span>${o.distanceKm} km</span>` : ""}
          ${unit ? `<span>${escapeHtml(String(unit))}</span>` : ""}
          ${o.updatedAt ? `<span>güncelleme ${escapeHtml(o.updatedAt)}</span>` : ""}
          ${o.discount ? `<span class="pill-discount">kaynak: indirimli</span>` : ""}
        </div>
        <div class="score-bars" title="Kaynak başlık/etiket metni taraması — laboratuvar sağlık skoru değil">
          ${scoreRow("Sağlık", o.healthScore)}
          ${scoreRow("Fiyat", o.economyScore)}
        </div>
        <div class="evidence-block">
          <span class="evidence-title">Etiket taraması</span>
          <ul class="evidence-list">
            ${(o.labelNotes || [])
              .slice(0, 1)
              .map((e) => `<li>${escapeHtml(e)}</li>`)
              .join("")}
            ${(o.labelEvidence || ["güçlü etiket sinyali yok (nötr)"])
              .slice(0, 4)
              .map((e) => `<li>${escapeHtml(e)}</li>`)
              .join("")}
          </ul>
          <button type="button" class="linkish detail-link" data-offer-id="${offerId}" data-detail-idx="${realIdx}">İçeriği / açıklamayı gör</button>
        </div>
      </div>
      <div class="offer-side">
        <div class="price-wrap">
          <div class="price ${best ? "best" : ""}">${money(o.price)}</div>
          ${best ? `<span class="best-badge">En uygun</span>` : ""}
          ${trendBadge(o)}
        </div>
        <button class="add-btn" data-idx="${realIdx}" data-offer-id="${offerId}">Sepete ekle</button>
      </div>
    </article>`;
}

function paintTable(offers) {
  const best = lowestPrice(offers);
  const rows = offers
    .map((o) => {
      const realIdx = findOfferIndex(o);
      const offerId = escapeHtml(String(o.id || ""));
      const isBest = isBestPrice(o, best);
      const unit =
        o.unitPriceEstimate != null
          ? unitPriceLabel(o).replace(/^≈\s*/, "")
          : o.unitPriceValue != null
            ? String(o.unitPriceValue)
            : "—";
      return `<tr class="${isBest ? "best-deal" : ""}" data-offer-id="${offerId}" data-detail-idx="${realIdx}">
        <td class="td-thumb">${productThumbHtml(o.imageUrl, "product-thumb thumb-sm")}</td>
        <td class="td-title"><button type="button" class="linkish detail-link" data-offer-id="${offerId}" data-detail-idx="${realIdx}">${escapeHtml(o.title)}</button>${o.volume ? `<div class="muted tiny">${escapeHtml(o.volume)}</div>` : ""}${isBest ? `<div><span class="best-badge">En uygun</span></div>` : ""}
          <div class="score-bars compact table-scores" title="${escapeHtml(o.analysisNote || "Etiket taraması")}">
            ${scoreRow("Sağlık", o.healthScore)}
            ${scoreRow("Fiyat", o.economyScore)}
          </div>
        </td>
        <td><span class="market-badge"><i style="background:${o.marketColor}"></i>${escapeHtml(o.marketLabel)}</span>
          ${o.depotName ? `<div class="muted tiny">${escapeHtml(o.depotName)}</div>` : ""}
        </td>
        <td class="td-num td-price ${isBest ? "best" : ""}">${money(o.price)}</td>
        <td class="td-num">${escapeHtml(String(unit))}</td>
        <td class="td-num">${o.distanceKm != null ? o.distanceKm + " km" : "—"}</td>
        <td>${trendBadge(o) || "—"}</td>
        <td><button class="add-btn compact" data-idx="${realIdx}" data-offer-id="${offerId}">Ekle</button></td>
      </tr>`;
    })
    .join("");
  return `<div class="table-wrap"><table class="price-table">
    <thead>
      <tr>
        <th></th>
        <th>Ürün</th>
        <th>Market / şube</th>
        <th>Fiyat</th>
        <th>Birim</th>
        <th>Uzaklık</th>
        <th>Trend</th>
        <th></th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

function paintGrouped(groups) {
  return groups
    .map((g, gi) => {
      const best = g.bestPrice != null ? Number(g.bestPrice) : lowestPrice(g.offers);
      const headImg =
        g.imageUrl ||
        (g.offers || []).map((o) => o.imageUrl).find(Boolean) ||
        "";
      const rows = g.offers
        .map((o) => {
          const realIdx = findOfferIndex(o);
          const offerId = escapeHtml(String(o.id || ""));
          const isBest = isBestPrice(o, best);
          return `<div class="group-row ${isBest ? "best-deal" : ""}" data-offer-id="${offerId}" data-detail-idx="${realIdx}" role="button" tabindex="0">
            ${productThumbHtml(o.imageUrl || headImg, "product-thumb thumb-sm")}
            <span class="market-badge"><i style="background:${o.marketColor}"></i>${escapeHtml(o.marketLabel)}</span>
            <span class="muted tiny">${o.depotName ? escapeHtml(o.depotName) : ""}${o.distanceKm != null ? ` · ${o.distanceKm} km` : ""}${isBest ? ` · En uygun` : ""}</span>
            <span class="group-price ${isBest ? "best" : ""}">${money(o.price)}</span>
            <span class="muted tiny" title="Tahmini birim fiyat (paket ÷ miktar)">${escapeHtml(unitPriceLabel(o) || o.unitPrice || "")}</span>
            <div class="score-bars compact" title="${escapeHtml(o.analysisNote || "Etiket metni taraması — laboratuvar skoru değil")}">
              ${scoreRow("Sağlık", o.healthScore)}
              ${scoreRow("Fiyat", o.economyScore)}
            </div>
            ${trendBadge(o)}
            <button class="add-btn compact" data-idx="${realIdx}" data-offer-id="${offerId}">Ekle</button>
            <div class="group-evidence muted tiny">${escapeHtml(((o.labelEvidence || [])[0] || "etiket taraması: nötr"))} · <button type="button" class="linkish detail-link" data-offer-id="${offerId}" data-detail-idx="${realIdx}">İçeriği gör</button></div>
          </div>`;
        })
        .join("");
      return `<section class="product-group" style="animation-delay:${Math.min(gi * 0.03, 0.4)}s">
        <header class="group-head">
          ${productThumbHtml(headImg)}
          <div>
            <h3>${escapeHtml(g.title || "")}</h3>
            <p class="muted">${escapeHtml([g.brand, g.volume].filter(Boolean).join(" · "))} · ${g.marketCount} market · en ucuz: ${escapeHtml(g.bestMarketLabel || "")} ${money(g.bestPrice)}</p>
          </div>
        </header>
        ${rows}
      </section>`;
    })
    .join("");
}

function paintOffers() {
  const offers = visibleOffers();
  if (!offers.length) {
    els.offerList.innerHTML =
      '<p class="muted">Bu konumda canlı fiyatlı teklif yok. Konumu veya ürün adını değiştirin.</p>';
    return;
  }

  if (state.viewMode === "table") {
    els.offerList.innerHTML = paintTable(offers);
    return;
  }
  const best = lowestPrice(offers);
  if (state.viewMode === "grouped") {
    const groups = visibleGroups();
    els.offerList.innerHTML = groups.length
      ? paintGrouped(groups)
      : offers.map((o, i) => offerCardHtml(o, i, best)).join("");
    return;
  }
  els.offerList.innerHTML = offers.map((o, i) => offerCardHtml(o, i, best)).join("");
}

function syncViewToggle() {
  els.viewToggle?.querySelectorAll(".view-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === state.viewMode);
  });
}

function offerIndexOf(o) {
  if (!o) return -1;
  return state.offers.findIndex(
    (x) =>
      x.id === o.id ||
      (x.title === o.title && x.marketId === o.marketId && x.price === o.price)
  );
}

function robotPickCard(label, entry, tone) {
  if (!entry?.offer) return "";
  const o = entry.offer;
  const idx = offerIndexOf(o);
  return `
    <article class="robot-pick ${tone || ""}">
      <span class="robot-pick-label">${escapeHtml(label)}</span>
      ${productThumbHtml(o.imageUrl, "product-thumb thumb-sm")}
      <p class="robot-pick-title">${escapeHtml(o.title || "")}</p>
      <p class="robot-pick-meta">
        <span class="market-badge"><i style="background:${o.marketColor || "#999"}"></i>${escapeHtml(o.marketLabel || "")}</span>
        <strong>${money(o.price)}</strong>
        ${o.volume ? `<span>${escapeHtml(o.volume)}</span>` : ""}
      </p>
      <div class="score-bars compact robot-bars">
        ${scoreRow("Sağlık", entry.healthScore ?? o.healthScore)}
        ${scoreRow("Fiyat", entry.economyScore ?? o.economyScore)}
      </div>
      ${
        idx >= 0
          ? `<button type="button" class="add-btn compact robot-add" data-idx="${idx}">Sepete ekle</button>`
          : ""
      }
    </article>`;
}

function renderRobot(robot) {
  if (!els.robotCard) return;
  if (!robot?.pick?.offer) {
    els.robotCard.hidden = true;
    els.robotCard.innerHTML = "";
    return;
  }
  const pick = robot.pick;
  const reasons = (pick.reasons || [])
    .slice(0, 4)
    .map((r) => `<li>${escapeHtml(r)}</li>`)
    .join("");
  els.robotCard.hidden = false;
  els.robotCard.innerHTML = `
    <div class="robot-head">
      <span class="robot-badge">Tüm marketler tarandı</span>
      <span class="robot-score">öneri skor ${pick.score ?? "—"}</span>
    </div>
    <div class="robot-picks">
      ${robotPickCard("En uygun", robot.bestPrice || pick, "tone-price")}
      ${robotPickCard("Kaliteli", robot.bestHealth || pick, "tone-health")}
      ${robotPickCard("Öneri", pick, "tone-rec")}
    </div>
    <h4 class="robot-why-title">${escapeHtml(pick.whyTitle || "Neden önerildi")}</h4>
    <ul class="robot-reasons">${reasons || "<li>Gerekçe üretilemedi</li>"}</ul>
    <p class="robot-disclaimer">${escapeHtml(robot.disclaimer || "")}</p>
  `;
}

function renderOffers(payload, opts = {}) {
  state.offers = mergeLocalPriceHistory(payload.offers || []);
  state.groups = payload.groups || [];
  const vol =
    opts.volume ||
    payload.activeVolume ||
    (opts.keepVolume ? state.activeVolume : null) ||
    "all";
  state.activeVolume = vol && vol !== "null" ? vol : "all";
  els.emptyState.hidden = true;
  els.resultsSection.hidden = false;
  els.resultsTitle.textContent = `“${payload.query}” sonuçları`;
  let metaText = `${payload.offerCount} canlı teklif · ${payload.source} · ${payload.location.distance} km · sıra: birim fiyat`;
  if (payload.typoCorrected && payload.originalQuery && payload.originalQuery !== payload.query) {
    metaText = `“${payload.originalQuery}” → “${payload.query}” · ` + metaText;
  }
  els.resultsMeta.textContent = metaText;

  const pills = Object.entries(payload.byMarket || {}).map(([id, count]) => {
    const m = state.markets.find((x) => x.id === id);
    return `<span class="pill">${m?.label || id}: ${count}</span>`;
  });
  if (payload.getir) {
    if (payload.getir.available) {
      pills.push(
        `<span class="pill">${escapeHtml(payload.getir.channelLabel || "Getir")}: ${payload.getir.offerCount || 0}</span>`
      );
    } else {
      pills.push(
        `<span class="pill warn">Getir: ${escapeHtml(payload.getir.note || "sonuç yok")}</span>`
      );
    }
  }
  pills.push(`<span class="pill">canlı şube · uydurma yok</span>`);
  els.statusRow.innerHTML = pills.join("");

  const volumes = [
    ...new Set(
      state.offers
        .map((o) => (o.volume || "").toUpperCase().replace("GR", "G").trim())
        .filter(Boolean)
    ),
  ].sort((a, b) => a.localeCompare(b, "tr"));
  renderVolumeChips(volumes);
  renderRobot(payload.robot);
  syncViewToggle();

  if (!state.offers.length) {
    els.offerList.innerHTML =
      '<p class="muted">Bu konumda canlı fiyatlı teklif yok.</p>';
    return;
  }
  paintOffers();
}

els.quickQueries?.addEventListener("click", (e) => {
  const btn = e.target.closest(".quick-chip");
  if (!btn) return;
  const q = btn.dataset.q || btn.textContent || "";
  if (els.query) els.query.value = q;
  lastCommittedQuery = String(q).trim();
  state.activeVolume = "all";
  runSearch(q);
});

let lastCommittedQuery = "";
let searchInFlight = false;

els.form?.addEventListener("submit", async (e) => {
  e.preventDefault();
  dismissKeyboard();
  const q = els.query?.value?.trim() || "";
  lastCommittedQuery = q;
  state.activeVolume = "all";
  await runSearch(q);
});

// Yazarken otomatik arama yok — sadece Ara / kg seçimi / ilçe
els.city?.addEventListener("change", () => {
  saveSelectedCity(els.city.value);
  const q = lastCommittedQuery || "";
  if (q.length < 2) return;
  const vol = state.activeVolume !== "all" ? state.activeVolume : null;
  runSearch(q, {
    volume: vol,
    keepVolume: true,
    auto: true,
    status: `Konum değişti · ${q}`,
  });
});

els.query?.addEventListener("focus", () => {
  els.query.removeAttribute("readonly");
  els.query.setAttribute("inputmode", "search");
});

els.query?.addEventListener("touchstart", () => {
  els.query.removeAttribute("readonly");
  els.query.setAttribute("inputmode", "search");
}, { passive: true });

async function runSearch(rawQuery, meta = {}) {
  const query = String(rawQuery || "").trim();
  if (!query) return;
  els.query.value = query;
  if (!meta.volume && !meta.keepVolume) {
    lastCommittedQuery = query;
  }
  dismissKeyboard();
  const city = selectedCity();
  if (!city?.lat || !city?.lon) {
    setScanStatus("İlçe seçilemedi — sayfayı yenileyin.", false);
    return;
  }
  const volume =
    meta.volume && meta.volume !== "all" ? String(meta.volume) : null;
  searchInFlight = true;
  els.searchBtn.disabled = true;
  els.searchBtn.textContent = meta.auto ? "…" : "Aranıyor…";
  const volNote = volume ? ` · ${volume}` : "";
  setScanStatus(meta.status || `Tüm marketlerde aranıyor: ${query}${volNote}`);
  try {
    const res = await apiFetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        latitude: city.lat,
        longitude: city.lon,
        distance: 12,
        volume,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Arama başarısız");
    if (data.query && data.query !== query) {
      els.query.value = data.query;
      if (!volume) lastCommittedQuery = data.query;
    }
    renderOffers(data, {
      volume: volume || "all",
      keepVolume: Boolean(meta.keepVolume || volume),
    });
    if (meta.note) setScanStatus(meta.note, false);
    else if (data.typoNote) setScanStatus(data.typoNote, false);
    else if (volume) setScanStatus(`${query} · ${volume}`, false);
    else setScanStatus("", true);
    dismissKeyboard();
    const el = els.resultsSection;
    if (el && !el.hidden) {
      const y = el.getBoundingClientRect().top + window.scrollY;
      const offset = document.getElementById("appChrome")?.offsetHeight ?? 0;
      window.scrollTo({ top: Math.max(0, y - offset - 6), behavior: "smooth" });
    }
    fitViewportToScreen();
  } catch (err) {
    els.emptyState.hidden = false;
    els.resultsSection.hidden = true;
    els.emptyState.innerHTML = `<p>Canlı arama hatası: ${escapeHtml(err.message)}</p>`;
    setScanStatus(err.message || "Arama hatası", false);
  } finally {
    searchInFlight = false;
    els.searchBtn.disabled = false;
    els.searchBtn.textContent = "Ara";
    dismissKeyboard();
    syncTimer();
  }
}

function setScanStatus(text, hide = false) {
  if (!els.scanStatus) return;
  if (hide || !text) {
    els.scanStatus.hidden = true;
    els.scanStatus.textContent = "";
    return;
  }
  els.scanStatus.hidden = false;
  els.scanStatus.textContent = text;
}

let html5QrLibPromise = null;
let tesseractPromise = null;
let liveScanner = null;
let scanBusy = false;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) {
      resolve();
      return;
    }
    const s = document.createElement("script");
    s.src = src;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`Script yüklenemedi: ${src}`));
    document.head.appendChild(s);
  });
}

async function ensureHtml5Qrcode() {
  if (window.Html5Qrcode) return window.Html5Qrcode;
  if (!html5QrLibPromise) {
    html5QrLibPromise = loadScript(
      "https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"
    ).then(() => {
      if (!window.Html5Qrcode) throw new Error("Barkod motoru yüklenemedi");
      return window.Html5Qrcode;
    });
  }
  return html5QrLibPromise;
}

async function ensureTesseract() {
  if (window.Tesseract) return window.Tesseract;
  if (!tesseractPromise) {
    tesseractPromise = loadScript(
      "https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js"
    ).then(() => {
      if (!window.Tesseract) throw new Error("OCR motoru yüklenemedi");
      return window.Tesseract;
    });
  }
  return tesseractPromise;
}

function cleanOcrQuery(text) {
  const lines = String(text || "")
    .split(/\n+/)
    .map((l) => l.replace(/[^\p{L}\p{N}\s.%/-]/gu, " ").replace(/\s+/g, " ").trim())
    .filter((l) => l.length >= 3);
  const stop = new Set([
    "içindekiler",
    "icerikler",
    "besin",
    "değer",
    "deger",
    "enerji",
    "protein",
    "yağ",
    "yag",
    "karbonhidrat",
    "üretici",
    "uretici",
    "ithalatçı",
    "ithalatci",
    "saklama",
    "son",
    "kullanma",
    "tarihi",
    "net",
    "ağırlık",
    "agirlik",
  ]);
  const scored = lines
    .map((l) => {
      const words = l.split(" ").filter((w) => w.length > 1 && !stop.has(w.toLowerCase()));
      return { l: words.join(" "), n: words.length };
    })
    .filter((x) => x.n >= 1)
    .sort((a, b) => b.n - a.n);
  const pick = scored.slice(0, 2).map((x) => x.l).join(" ").trim();
  return pick.slice(0, 80);
}

async function lookupBarcodeAndSearch(code) {
  setScanStatus(`Barkod okundu: ${code} · ürün adı aranıyor…`);
  const res = await apiFetch(`/api/barcode/${encodeURIComponent(code)}`);
  const data = await res.json();
  const query = data.query || code;
  await runSearch(query, {
    note: data.note || `Barkod ${code} ile arandı.`,
    status: `Barkod → ${query}`,
  });
}

async function ocrImageAndSearch(file) {
  setScanStatus("Barkod yok · etiket metni okunuyor (OCR)…");
  const Tesseract = await ensureTesseract();
  const result = await Tesseract.recognize(file, "tur+eng", {
    logger: (m) => {
      if (m.status === "recognizing text" && els.scanStatus) {
        const pct = Math.round((m.progress || 0) * 100);
        els.scanStatus.textContent = `Etiket okunuyor… %${pct}`;
      }
    },
  });
  const query = cleanOcrQuery(result?.data?.text || "");
  if (!query || query.length < 3) {
    setScanStatus(
      "Fotoğraftan ürün adı okunamadı. Daha net çekin veya elle yazın.",
      false
    );
    return;
  }
  await runSearch(query, {
    note: `Etiketten okunan metinle arandı: “${query}”`,
    status: `OCR → ${query}`,
  });
}

async function processScanFile(file) {
  if (!file || scanBusy) return;
  scanBusy = true;
  try {
    setScanStatus("Görüntü işleniyor…");
    const Html5Qrcode = await ensureHtml5Qrcode();
    // gizli reader elemanı
    let holder = document.getElementById("scanFileReader");
    if (!holder) {
      holder = document.createElement("div");
      holder.id = "scanFileReader";
      holder.hidden = true;
      document.body.appendChild(holder);
    }
    const scanner = new Html5Qrcode("scanFileReader");
    try {
      const decoded = await scanner.scanFile(file, false);
      await scanner.clear().catch(() => {});
      if (decoded) {
        await lookupBarcodeAndSearch(String(decoded).trim());
        return;
      }
    } catch {
      await scanner.clear().catch(() => {});
    }
    await ocrImageAndSearch(file);
  } catch (err) {
    setScanStatus(err.message || "Tarama başarısız", false);
  } finally {
    scanBusy = false;
    if (els.scanFileInput) els.scanFileInput.value = "";
    if (els.scanGalleryInput) els.scanGalleryInput.value = "";
  }
}

async function openLiveScanner() {
  const Html5Qrcode = await ensureHtml5Qrcode();
  if (!els.scanModal) return;
  els.scanModal.hidden = false;
  els.scanModal.setAttribute("aria-hidden", "false");
  if (els.scanLiveStatus) els.scanLiveStatus.textContent = "Kamera açılıyor…";
  const formats = window.Html5QrcodeSupportedFormats
    ? [
        window.Html5QrcodeSupportedFormats.EAN_13,
        window.Html5QrcodeSupportedFormats.EAN_8,
        window.Html5QrcodeSupportedFormats.UPC_A,
        window.Html5QrcodeSupportedFormats.UPC_E,
        window.Html5QrcodeSupportedFormats.CODE_128,
        window.Html5QrcodeSupportedFormats.QR_CODE,
      ]
    : undefined;
  liveScanner = new Html5Qrcode("scanReader", formats ? { formatsToSupport: formats } : undefined);
  try {
    await liveScanner.start(
      { facingMode: "environment" },
      { fps: 8, qrbox: { width: 260, height: 160 } },
      async (decodedText) => {
        if (scanBusy) return;
        scanBusy = true;
        try {
          await stopLiveScanner();
          await lookupBarcodeAndSearch(String(decodedText).trim());
        } finally {
          scanBusy = false;
        }
      },
      () => {}
    );
    if (els.scanLiveStatus) {
      els.scanLiveStatus.textContent = "Barkodu çerçeveye hizalayın.";
    }
  } catch (err) {
    if (els.scanLiveStatus) {
      els.scanLiveStatus.textContent =
        err?.message ||
        "Kamera açılamadı. Galeri/foto seçeneğini kullanın veya tarayıcı izni verin.";
    }
  }
}

async function stopLiveScanner() {
  if (liveScanner) {
    try {
      await liveScanner.stop();
    } catch {
      /* ignore */
    }
    try {
      await liveScanner.clear();
    } catch {
      /* ignore */
    }
    liveScanner = null;
  }
  if (els.scanModal) {
    els.scanModal.hidden = true;
    els.scanModal.setAttribute("aria-hidden", "true");
  }
}

els.scanLiveBtn?.addEventListener("click", () => {
  openLiveScanner().catch((err) => {
    setScanStatus(err?.message || "Canlı tarayıcı açılamadı", false);
  });
});

els.scanFileInput?.addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  if (file) processScanFile(file);
});

els.scanGalleryInput?.addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  if (file) processScanFile(file);
});

function setListStatus(text, hide = false) {
  if (!els.listScanStatus) return;
  if (hide) {
    els.listScanStatus.hidden = true;
    els.listScanStatus.textContent = "";
    return;
  }
  els.listScanStatus.hidden = false;
  els.listScanStatus.textContent = text;
}

function renderMissing(items) {
  state.missingItems = items || [];
  if (!els.missingSection || !els.missingList) return;
  if (!state.missingItems.length) {
    els.missingSection.hidden = true;
    els.missingList.innerHTML = "";
    return;
  }
  els.missingSection.hidden = false;
  els.missingList.innerHTML = state.missingItems
    .map((row, idx) => {
      const sims = row.similars || [];
      return `
      <article class="missing-card" data-missing-idx="${idx}">
        <div class="missing-head">
          <strong>${escapeHtml(row.listItem || row.query || "—")}</strong>
          <span class="muted tiny">${escapeHtml(row.reason || "Bulunamadı")}</span>
        </div>
        ${
          sims.length
            ? `<div class="missing-sims">
                <p class="muted tiny">Benzer öneriler:</p>
                ${sims
                  .map(
                    (s, si) => `
                  <div class="missing-sim-row">
                    <div>
                      <div>${escapeHtml(s.title || "")}</div>
                      <div class="muted tiny">${escapeHtml(s.marketLabel || "")} · ${money(s.price)}${s.volume ? ` · ${escapeHtml(s.volume)}` : ""}${s.brand ? ` · ${escapeHtml(s.brand)}` : ""}</div>
                      <div class="similar-note">Benzeri: aranan “${escapeHtml(row.listItem || row.query)}”</div>
                    </div>
                    <button type="button" class="add-btn" data-missing-idx="${idx}" data-sim-idx="${si}">İstersen ekle</button>
                  </div>`
                  )
                  .join("")}
              </div>`
            : `<p class="muted tiny">Benzer aday da yok.</p>`
        }
      </article>`;
    })
    .join("");
}

async function runListScan(rawText) {
  const text = String(rawText || "").trim();
  if (!text) {
    setListStatus("Liste boş — satır yazın veya fotoğraf yükleyin.", false);
    return;
  }
  const city = selectedCity();
  if (els.listScanBtn) {
    els.listScanBtn.disabled = true;
    els.listScanBtn.textContent = "Taranıyor…";
  }
  setListStatus("Liste taranıyor (marka + kg + en ucuz)…");
  dismissKeyboard();
  try {
    const res = await apiFetch("/api/list-scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        latitude: city.lat,
        longitude: city.lon,
        distance: 12,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Liste taraması başarısız");

    let added = 0;
    for (const row of data.matched || []) {
      const offer = row.offer;
      if (!offer) continue;
      addToCart(offer, {
        listItem: row.listItem,
        matchType: row.matchType,
        similarNote: row.similarNote,
        openDrawer: false,
      });
      added += 1;
    }
    renderMissing(data.unmatched || []);
    renderCarts();
    if (added) openDrawer(true);
    els.emptyState.hidden = true;
    setListStatus(
      `${data.matchedCount}/${data.itemCount} sepete eklendi · ${data.unmatchedCount} bulunamayan` +
        (data.note ? ` · ${data.note}` : ""),
      false
    );
    if (els.listText && data.lines) {
      els.listText.value = (data.lines || []).join("\n");
    }
  } catch (err) {
    setListStatus(err.message || "Liste hatası", false);
  } finally {
    if (els.listScanBtn) {
      els.listScanBtn.disabled = false;
      els.listScanBtn.textContent = "Listeyi tara ve sepetlere ekle";
    }
  }
}

async function ocrListImage(file) {
  if (!file) return;
  setListStatus("Liste fotoğrafı okunuyor (OCR)…");
  const Tesseract = await ensureTesseract();
  const result = await Tesseract.recognize(file, "tur+eng", {
    logger: (m) => {
      if (m.status === "recognizing text" && els.listScanStatus) {
        const pct = Math.round((m.progress || 0) * 100);
        els.listScanStatus.hidden = false;
        els.listScanStatus.textContent = `Liste okunuyor… %${pct}`;
      }
    },
  });
  const text = (result?.data?.text || "")
    .split(/\r?\n/)
    .map((l) => l.replace(/[^\wğüşıöçĞÜŞİÖÇ\s.\-%/]/gi, " ").trim())
    .filter((l) => l.length >= 2)
    .join("\n");
  if (!text) {
    setListStatus("Fotoğraftan liste okunamadı. Daha net çekin veya elle yazın.", false);
    return;
  }
  if (els.listText) els.listText.value = text;
  await runListScan(text);
}

els.listScanBtn?.addEventListener("click", () => runListScan(els.listText?.value || ""));

els.listPasteBtn?.addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (!text?.trim()) {
      setListStatus("Pano boş. Önce listeyi kopyalayın.", false);
      return;
    }
    const cur = (els.listText?.value || "").trim();
    els.listText.value = cur ? `${cur}\n${text.trim()}` : text.trim();
    setListStatus("Liste panodan yapıştırıldı. “Listeyi tara”ya basın.", false);
    els.listText?.focus();
  } catch {
    els.listText?.focus();
    setListStatus(
      "Otomatik yapıştırma engelli. Kutuya dokunup Yapıştır / Ctrl+V / uzun bas kullanın.",
      false
    );
  }
});

els.listText?.addEventListener("paste", () => {
  setTimeout(() => {
    setListStatus("Yapıştırıldı. “Listeyi tara ve sepetlere ekle”ye basın.", false);
  }, 0);
});

els.listFileInput?.addEventListener("change", (e) => {
  const f = e.target.files?.[0];
  if (f) ocrListImage(f);
  e.target.value = "";
});
els.listGalleryInput?.addEventListener("change", (e) => {
  const f = e.target.files?.[0];
  if (f) ocrListImage(f);
  e.target.value = "";
});

els.missingList?.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-missing-idx][data-sim-idx]");
  if (!btn) return;
  const mi = Number(btn.dataset.missingIdx);
  const si = Number(btn.dataset.simIdx);
  const row = state.missingItems[mi];
  const offer = row?.similars?.[si];
  if (!offer) return;
  addToCart(offer, {
    listItem: row.listItem,
    matchType: "similar",
    similarNote: `Benzeri: aranan “${row.listItem || row.query}”`,
  });
  setListStatus(`Benzer eklendi: ${offer.title}`, false);
});

els.closeScanModal?.addEventListener("click", () => stopLiveScanner());
els.scanModal?.addEventListener("click", (e) => {
  if (e.target === els.scanModal) stopLiveScanner();
});

els.offerList?.addEventListener("click", (e) => {
  const btn = e.target.closest(".add-btn");
  if (btn) {
    e.preventDefault();
    e.stopPropagation();
    const offer = offerByIdxOrId(btn);
    if (offer) addToCart(offer);
    return;
  }
  const detail = e.target.closest("[data-offer-id], [data-detail-idx], .detail-link");
  if (!detail) return;
  // Don't treat random nested clicks without id as detail if only on add area already handled
  const offer = offerByIdxOrId(detail.closest("[data-offer-id]") || detail);
  if (offer) {
    e.preventDefault();
    showProductContent(offer);
  }
});

els.offerList?.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const row = e.target.closest("[data-offer-id]");
  if (!row || e.target.closest("button")) return;
  e.preventDefault();
  const offer = offerByIdxOrId(row);
  if (offer) showProductContent(offer);
});

els.productModalBody?.addEventListener("click", (e) => {
  const btn = e.target.closest(".add-btn");
  if (!btn) return;
  const offer = offerByIdxOrId(btn);
  if (offer) addToCart(offer);
});

els.closeProductModal?.addEventListener("click", () => openProductModal(false));
els.productModal?.addEventListener("click", (e) => {
  if (e.target === els.productModal) openProductModal(false);
});

els.robotCard?.addEventListener("click", (e) => {
  const btn = e.target.closest(".add-btn");
  if (!btn) return;
  const offer = offerByIdxOrId(btn);
  if (offer) addToCart(offer);
});

els.volumeRow?.addEventListener("click", (e) => {
  const btn = e.target.closest(".vol-chip");
  if (!btn) return;
  const vol = btn.dataset.volume || "all";
  state.activeVolume = vol;
  renderVolumeChips(state.volumeOptions);
  const q = lastCommittedQuery || String(els.query?.value || "").trim();
  if (q.length < 2) {
    paintOffers();
    return;
  }
  // kg / hacim seçince otomatik yeniden ara (yazarken değil)
  runSearch(q, {
    volume: vol === "all" ? null : vol,
    keepVolume: true,
    auto: true,
    status: vol === "all" ? `Tümü · ${q}` : `${q} · ${vol}`,
  });
});

els.viewToggle?.addEventListener("click", (e) => {
  const btn = e.target.closest(".view-btn");
  if (!btn) return;
  state.viewMode = btn.dataset.view || "grouped";
  syncViewToggle();
  paintOffers();
});

els.cartPanels?.addEventListener("click", (e) => {
  const removeBtn = e.target.closest(".remove-item-btn");
  if (removeBtn) {
    removeFromCart(removeBtn.dataset.market, removeBtn.dataset.id);
    return;
  }
  const btn = e.target.closest(".qty-btn");
  if (!btn) return;
  changeQty(btn.dataset.market, btn.dataset.id, Number(btn.dataset.delta));
});

async function downloadCartsPdf() {
  if (!els.downloadCartPdf || !Object.keys(state.carts).length) return;
  const city = selectedCity();
  els.downloadCartPdf.disabled = true;
  if (els.pdfMsg) {
    els.pdfMsg.hidden = false;
    els.pdfMsg.textContent = "PDF hazırlanıyor…";
  }
  try {
    const res = await apiFetch("/api/carts/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        carts: state.carts,
        cityLabel: city?.label || "Ankara",
        note: `Oluşturma: ${new Date().toLocaleString("tr-TR")}`,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "PDF indirilemedi");
    }
    const blob = await res.blob();
    const stamp = new Date()
      .toISOString()
      .slice(0, 16)
      .replace("T", "_")
      .replace(":", "-");
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sepetkiyas-sepetler-${stamp}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    if (els.pdfMsg) els.pdfMsg.textContent = "PDF indirildi.";
  } catch (err) {
    if (els.pdfMsg) els.pdfMsg.textContent = err.message || "PDF hatası";
  } finally {
    els.downloadCartPdf.disabled = !Object.keys(state.carts).length;
  }
}

els.downloadCartPdf?.addEventListener("click", () => {
  downloadCartsPdf();
});

els.cartToggle?.addEventListener("click", () => openDrawer(true));
els.closeCart?.addEventListener("click", () => openDrawer(false));
els.scrim?.addEventListener("click", () => openDrawer(false));
els.tabCart?.addEventListener("click", () => openDrawer(true));
els.clearCarts?.addEventListener("click", () => {
  state.carts = {};
  saveCarts();
  renderCarts();
});

els.desktopBtn?.addEventListener("click", async () => {
  if (els.desktopMsg) els.desktopMsg.textContent = "Ekleniyor…";
  try {
    const res = await apiFetch("/api/install-desktop", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Kısayol eklenemedi");
    if (els.desktopMsg) els.desktopMsg.textContent = data.message || "Masaüstüne eklendi.";
  } catch (err) {
    if (els.desktopMsg) els.desktopMsg.textContent = err.message;
  }
});

// Global yedek API — HTML / konsol / eski cache kurtarma
window.AGT = {
  search: (q) => runSearch(q || els.query?.value || ""),
  listScan: () => runListScan(els.listText?.value || ""),
  pasteList: async () => {
    const btn = els.listPasteBtn;
    if (btn) btn.click();
  },
  geo: () => autoSelectByGeolocation(true),
  openCart: () => openDrawer(true),
  closeCart: () => openDrawer(false),
  unlock: () => unlockGate(),
  build: "30",
};
window.__AGT_READY = true;
hideBootBanner();

boot().catch((err) => {
  console.error(err);
  if (els.emptyState) {
    els.emptyState.hidden = false;
    els.emptyState.innerHTML = `<p>Uygulama başlatılamadı: ${escapeHtml(err.message)}</p>`;
  }
});
