const state = {
  markets: [],
  cities: [],
  offers: [],
  groups: [],
  volumeOptions: [],
  activeVolume: "all",
  viewMode: "grouped",
  carts: loadCarts(),
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
  installHint: document.getElementById("installHint"),
  installBtn: document.getElementById("installBtn"),
  desktopBtn: document.getElementById("desktopBtn"),
  desktopMsg: document.getElementById("desktopMsg"),
  tabSearch: document.getElementById("tabSearch"),
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
    const res = await fetch("/api/timer", { cache: "no-store" });
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
  return state.cities.find((c) => c.id === els.city.value) || state.cities[0];
}

function registerPwa() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

function setupInstall() {
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    state.deferredPrompt = e;
    els.installHint.hidden = false;
  });

  els.installBtn?.addEventListener("click", async () => {
    if (!state.deferredPrompt) return;
    state.deferredPrompt.prompt();
    await state.deferredPrompt.userChoice;
    state.deferredPrompt = null;
    els.installHint.hidden = true;
  });

  // iOS Safari: show soft tip
  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone;
  if (isIos && !isStandalone) {
    els.installHint.hidden = false;
    els.installBtn.textContent = "Ana ekrana ekle";
    els.installBtn.onclick = () => {
      alert("Safari’de Paylaş → Ana Ekrana Ekle ile SepetKıyas’ı yükleyebilirsiniz.");
    };
  }
}

async function boot() {
  fitViewportToScreen();
  window.addEventListener("resize", fitViewportToScreen);
  window.visualViewport?.addEventListener("resize", fitViewportToScreen);
  window.visualViewport?.addEventListener("scroll", fitViewportToScreen);

  registerPwa();
  setupInstall();
  startTimerLoop();

  if (new URLSearchParams(location.search).get("focus") === "search") {
    els.query.focus();
  }

  const res = await fetch("/api/markets");
  const data = await res.json();
  state.markets = data.markets;
  state.cities = data.cities;

  els.city.innerHTML = state.cities
    .map((c) => `<option value="${c.id}">${c.label}</option>`)
    .join("");

  if (els.quickQueries) {
    const qs = data.quickQueries || [];
    els.quickQueries.innerHTML = qs
      .map(
        (q) =>
          `<button type="button" class="quick-chip" data-q="${escapeHtml(q)}">${escapeHtml(q)}</button>`
      )
      .join("");
  }

  els.chips.innerHTML = state.markets
    .map(
      (m) => `
      <span class="chip ${m.live ? "live" : ""}" title="${escapeHtml(m.hint || "")}">
        <span class="dot" style="background:${m.color}"></span>
        ${m.label}
        <span class="tag">${m.live ? "canlı" : "bekleniyor"}</span>
      </span>`
    )
    .join("");

  renderCarts();
}

function openDrawer(open) {
  els.cartDrawer.classList.toggle("open", open);
  els.cartDrawer.setAttribute("aria-hidden", String(!open));
  els.cartToggle.setAttribute("aria-expanded", String(open));
  els.scrim.hidden = !open;
  els.tabSearch.classList.toggle("active", !open);
  els.tabCart.classList.toggle("active", open);
}

function addToCart(offer) {
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
    });
  }
  saveCarts();
  renderCarts();
  openDrawer(true);
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
              <div>
                <div>${escapeHtml(item.title)}</div>
                <div class="muted tiny">${money(item.price)} × ${item.qty}</div>
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
      ${
        offer.imageUrl
          ? `<img src="${offer.imageUrl}" alt="" loading="lazy" />`
          : ""
      }
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
    const res = await fetch("/api/product-content", {
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
  const realIdx = state.offers.indexOf(o);
  const best = isBestPrice(o, bestPrice);
  const img = o.imageUrl
    ? `<img src="${o.imageUrl}" alt="" loading="lazy" />`
    : `<div style="width:72px;height:72px;border-radius:12px;background:#0b140f"></div>`;
  const valueBadge = o.valuePick
    ? `<span class="value-badge">Tahmin: uygun fiyat + sade etiket</span>`
    : "";
  const unit = unitPriceLabel(o);
  return `
    <article class="offer ${o.valuePick ? "value-pick" : ""} ${best ? "best-deal" : ""}" data-detail-idx="${realIdx}" style="animation-delay:${Math.min(idx * 0.03, 0.4)}s">
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
          <button type="button" class="linkish detail-link" data-detail-idx="${realIdx}">İçeriği / açıklamayı gör</button>
        </div>
      </div>
      <div class="offer-side">
        <div class="price-wrap">
          <div class="price ${best ? "best" : ""}">${money(o.price)}</div>
          ${best ? `<span class="best-badge">En uygun</span>` : ""}
          ${trendBadge(o)}
        </div>
        <button class="add-btn" data-idx="${realIdx}">Sepete ekle</button>
      </div>
    </article>`;
}

function paintTable(offers) {
  const best = lowestPrice(offers);
  const rows = offers
    .map((o) => {
      const realIdx = state.offers.indexOf(o);
      const isBest = isBestPrice(o, best);
      const unit =
        o.unitPriceEstimate != null
          ? unitPriceLabel(o).replace(/^≈\s*/, "")
          : o.unitPriceValue != null
            ? String(o.unitPriceValue)
            : "—";
      return `<tr class="${isBest ? "best-deal" : ""}">
        <td class="td-title"><button type="button" class="linkish detail-link" data-detail-idx="${realIdx}">${escapeHtml(o.title)}</button>${o.volume ? `<div class="muted tiny">${escapeHtml(o.volume)}</div>` : ""}${isBest ? `<div><span class="best-badge">En uygun</span></div>` : ""}
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
        <td><button class="add-btn compact" data-idx="${realIdx}">Ekle</button></td>
      </tr>`;
    })
    .join("");
  return `<div class="table-wrap"><table class="price-table">
    <thead>
      <tr>
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
      const rows = g.offers
        .map((o) => {
          const realIdx = state.offers.indexOf(o);
          const isBest = isBestPrice(o, best);
          return `<div class="group-row ${isBest ? "best-deal" : ""}" data-detail-idx="${realIdx}">
            <span class="market-badge"><i style="background:${o.marketColor}"></i>${escapeHtml(o.marketLabel)}</span>
            <span class="muted tiny">${o.depotName ? escapeHtml(o.depotName) : ""}${o.distanceKm != null ? ` · ${o.distanceKm} km` : ""}${isBest ? ` · En uygun` : ""}</span>
            <span class="group-price ${isBest ? "best" : ""}">${money(o.price)}</span>
            <span class="muted tiny" title="Tahmini birim fiyat (paket ÷ miktar)">${escapeHtml(unitPriceLabel(o) || o.unitPrice || "")}</span>
            <div class="score-bars compact" title="${escapeHtml(o.analysisNote || "Etiket metni taraması — laboratuvar skoru değil")}">
              ${scoreRow("Sağlık", o.healthScore)}
              ${scoreRow("Fiyat", o.economyScore)}
            </div>
            ${trendBadge(o)}
            <button class="add-btn compact" data-idx="${realIdx}">Ekle</button>
            <div class="group-evidence muted tiny">${escapeHtml(((o.labelEvidence || [])[0] || "etiket taraması: nötr"))} · <button type="button" class="linkish detail-link" data-detail-idx="${realIdx}">İçeriği gör</button></div>
          </div>`;
        })
        .join("");
      return `<section class="product-group" style="animation-delay:${Math.min(gi * 0.03, 0.4)}s">
        <header class="group-head">
          ${g.imageUrl ? `<img src="${g.imageUrl}" alt="" loading="lazy" />` : ""}
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

function renderRobot(robot) {
  if (!els.robotCard) return;
  if (!robot?.pick?.offer) {
    els.robotCard.hidden = true;
    els.robotCard.innerHTML = "";
    return;
  }
  const pick = robot.pick;
  const o = pick.offer;
  const reasons = (pick.reasons || [])
    .map((r) => `<li>${escapeHtml(r)}</li>`)
    .join("");
  const alt = (robot.alternatives || [])
    .map(
      (a) =>
        `<span class="robot-alt">${escapeHtml(a.offer.marketLabel)} · ${money(a.offer.price)} · sağlık ${a.healthScore ?? "—"}%</span>`
    )
    .join("");
  const idx = state.offers.findIndex(
    (x) => x.id === o.id || (x.title === o.title && x.marketId === o.marketId && x.price === o.price)
  );
  els.robotCard.hidden = false;
  els.robotCard.innerHTML = `
    <div class="robot-head">
      <span class="robot-badge">Kıyas robotu · öneri</span>
      <span class="robot-score">skor ${pick.score}</span>
    </div>
    <p class="robot-title">${escapeHtml(o.title)}</p>
    <p class="robot-summary">${escapeHtml(pick.summary || "")}</p>
    <div class="score-bars robot-bars" title="${escapeHtml(o.analysisNote || "Etiket metni taraması")}">
      ${scoreRow("Sağlık", pick.healthScore)}
      ${scoreRow("Fiyat", pick.economyScore)}
    </div>
    <h4 class="robot-why-title">${escapeHtml(pick.whyTitle || "Neden önerildi")}</h4>
    <ul class="robot-reasons">${reasons || "<li>Gerekçe üretilemedi</li>"}</ul>
    <div class="robot-meta">
      <span class="market-badge"><i style="background:${o.marketColor || "#999"}"></i>${escapeHtml(o.marketLabel)}</span>
      <strong class="robot-price">${money(o.price)}</strong>
      ${o.volume ? `<span>${escapeHtml(o.volume)}</span>` : ""}
      ${unitPriceLabel(o) ? `<span>${escapeHtml(unitPriceLabel(o))}</span>` : ""}
    </div>
    ${alt ? `<div class="robot-alts">Alternatif: ${alt}</div>` : ""}
    <p class="robot-disclaimer">${escapeHtml(robot.disclaimer || "")}</p>
    ${
      idx >= 0
        ? `<button type="button" class="add-btn robot-add" data-idx="${idx}">Önerileni sepete ekle</button>`
        : ""
    }
  `;
}

function renderOffers(payload) {
  state.offers = mergeLocalPriceHistory(payload.offers || []);
  state.groups = payload.groups || [];
  state.activeVolume = "all";
  els.emptyState.hidden = true;
  els.resultsSection.hidden = false;
  els.resultsTitle.textContent = `“${payload.query}” sonuçları`;
  els.resultsMeta.textContent = `${payload.offerCount} canlı teklif · ${payload.source} · ${payload.location.distance} km · sıra: birim fiyat`;

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
  els.query.value = btn.dataset.q || btn.textContent || "";
  els.form.requestSubmit();
});

els.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = els.query.value.trim();
  if (!query) return;
  const city = selectedCity();
  els.searchBtn.disabled = true;
  els.searchBtn.textContent = "Taranıyor…";
  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        latitude: city.lat,
        longitude: city.lon,
        distance: 10,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Arama başarısız");
    renderOffers(data);
  } catch (err) {
    els.emptyState.hidden = false;
    els.resultsSection.hidden = true;
    els.emptyState.innerHTML = `<p>Canlı arama hatası: ${escapeHtml(err.message)}</p>`;
  } finally {
    els.searchBtn.disabled = false;
    els.searchBtn.textContent = "Karşılaştır";
    syncTimer();
  }
});

els.offerList.addEventListener("click", (e) => {
  const detail = e.target.closest("[data-detail-idx]");
  const btn = e.target.closest(".add-btn");
  if (btn) {
    e.stopPropagation();
    const offer = state.offers[Number(btn.dataset.idx)];
    if (offer) addToCart(offer);
    return;
  }
  if (detail) {
    const offer = state.offers[Number(detail.dataset.detailIdx)];
    if (offer) showProductContent(offer);
  }
});

els.productModalBody?.addEventListener("click", (e) => {
  const btn = e.target.closest(".add-btn");
  if (!btn) return;
  const offer = state.offers[Number(btn.dataset.idx)];
  if (offer) addToCart(offer);
});

els.closeProductModal?.addEventListener("click", () => openProductModal(false));
els.productModal?.addEventListener("click", (e) => {
  if (e.target === els.productModal) openProductModal(false);
});

els.robotCard?.addEventListener("click", (e) => {
  const btn = e.target.closest(".add-btn");
  if (!btn) return;
  const offer = state.offers[Number(btn.dataset.idx)];
  if (offer) addToCart(offer);
});

els.volumeRow?.addEventListener("click", (e) => {
  const btn = e.target.closest(".vol-chip");
  if (!btn) return;
  state.activeVolume = btn.dataset.volume || "all";
  renderVolumeChips(state.volumeOptions);
  paintOffers();
});

els.viewToggle?.addEventListener("click", (e) => {
  const btn = e.target.closest(".view-btn");
  if (!btn) return;
  state.viewMode = btn.dataset.view || "grouped";
  syncViewToggle();
  paintOffers();
});

els.cartPanels.addEventListener("click", (e) => {
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
    const res = await fetch("/api/carts/pdf", {
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

els.cartToggle.addEventListener("click", () => openDrawer(true));
els.closeCart.addEventListener("click", () => openDrawer(false));
els.scrim.addEventListener("click", () => openDrawer(false));
els.tabSearch?.addEventListener("click", () => {
  openDrawer(false);
  els.query.focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
});
els.tabCart?.addEventListener("click", () => openDrawer(true));
els.clearCarts.addEventListener("click", () => {
  state.carts = {};
  saveCarts();
  renderCarts();
});

els.desktopBtn?.addEventListener("click", async () => {
  els.desktopMsg.textContent = "Ekleniyor…";
  try {
    const res = await fetch("/api/install-desktop", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Kısayol eklenemedi");
    els.desktopMsg.textContent = data.message || "Masaüstüne eklendi.";
  } catch (err) {
    els.desktopMsg.textContent = err.message;
  }
});

boot().catch((err) => {
  els.emptyState.innerHTML = `<p>Uygulama başlatılamadı: ${escapeHtml(err.message)}</p>`;
});
