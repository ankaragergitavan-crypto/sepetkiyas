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
  grandTotal: document.getElementById("grandTotal"),
  viewToggle: document.getElementById("viewToggle"),
  clearCarts: document.getElementById("clearCarts"),
  installHint: document.getElementById("installHint"),
  installBtn: document.getElementById("installBtn"),
  desktopBtn: document.getElementById("desktopBtn"),
  desktopMsg: document.getElementById("desktopMsg"),
  tabSearch: document.getElementById("tabSearch"),
  tabCart: document.getElementById("tabCart"),
  liveTimer: document.getElementById("liveTimer"),
  liveTimerValue: document.getElementById("liveTimerValue"),
  quickQueries: document.getElementById("quickQueries"),
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
    els.cartPanels.innerHTML =
      '<p class="muted">Henüz ürün yok. Sonuçlardan “Sepete ekle” ile market bazlı sepet doldurun.</p>';
    return;
  }

  const totals = ids.map((marketId) => {
    const items = state.carts[marketId];
    const total = items.reduce((s, i) => s + i.price * i.qty, 0);
    return { marketId, total, items };
  });
  totals.sort((a, b) => a.total - b.total);
  const winner = totals[0];
  if (els.cartWinner) {
    const meta = marketMap[winner.marketId];
    els.cartWinner.hidden = false;
    els.cartWinner.innerHTML = `En ucuz sepet: <strong>${escapeHtml(meta?.label || winner.marketId)}</strong> · ${money(winner.total)}`;
  }

  els.cartPanels.innerHTML = totals
    .map(({ marketId, total, items }) => {
      const meta = marketMap[marketId];
      const isWin = marketId === winner.marketId;
      return `
        <section class="cart-panel ${isWin ? "winner" : ""}">
          <h3>
            <span class="market-badge">
              <i style="background:${meta?.color || "#999"}"></i>
              ${meta?.label || marketId}${isWin ? " · en ucuz" : ""}
            </span>
            <span>${items.reduce((s, i) => s + i.qty, 0)} ürün</span>
          </h3>
          ${items
            .map(
              (item) => `
            <div class="cart-item">
              <div>
                <div>${escapeHtml(item.title)}</div>
                <div class="qty-row">
                  <button class="qty-btn" data-market="${marketId}" data-id="${item.id}" data-delta="-1">−</button>
                  <span>${item.qty}</span>
                  <button class="qty-btn" data-market="${marketId}" data-id="${item.id}" data-delta="1">+</button>
                </div>
              </div>
              <div class="line-total">${money(item.price * item.qty)}</div>
            </div>`
            )
            .join("")}
          <div class="panel-total"><span>Sepet toplamı</span><span>${money(total)}</span></div>
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
  const s = Math.max(0, Math.min(100, Number(score) || 0));
  const hue = Math.round((s / 100) * 120);
  return `
    <div class="score-row">
      <span class="score-label">${label}</span>
      <div class="bar-track"><i style="width:${s}%;background:hsl(${hue} 75% 48%)"></i></div>
      <span class="score-num">${s}</span>
    </div>`;
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
  const unit =
    o.unitPriceEstimate != null
      ? `≈ ${Number(o.unitPriceEstimate).toFixed(0)} ₺/birim`
      : o.unitPrice || "";
  return `
    <article class="offer ${o.valuePick ? "value-pick" : ""} ${best ? "best-deal" : ""}" style="animation-delay:${Math.min(idx * 0.03, 0.4)}s">
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
        <div class="score-bars" title="Kaynak metni taraması — laboratuvar skoru değil">
          ${scoreRow("Etiket", o.healthScore)}
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
          ? `${Number(o.unitPriceEstimate).toFixed(0)}`
          : o.unitPriceValue != null
            ? String(o.unitPriceValue)
            : "—";
      return `<tr class="${isBest ? "best-deal" : ""}">
        <td class="td-title">${escapeHtml(o.title)}${o.volume ? `<div class="muted tiny">${escapeHtml(o.volume)}</div>` : ""}${isBest ? `<div><span class="best-badge">En uygun</span></div>` : ""}</td>
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
          return `<div class="group-row ${isBest ? "best-deal" : ""}">
            <span class="market-badge"><i style="background:${o.marketColor}"></i>${escapeHtml(o.marketLabel)}</span>
            <span class="muted tiny">${o.depotName ? escapeHtml(o.depotName) : ""}${o.distanceKm != null ? ` · ${o.distanceKm} km` : ""}${isBest ? ` · En uygun` : ""}</span>
            <span class="group-price ${isBest ? "best" : ""}">${money(o.price)}</span>
            <span class="muted tiny">${o.unitPriceEstimate != null ? `≈ ${Number(o.unitPriceEstimate).toFixed(0)} birim` : o.unitPrice || ""}</span>
            ${trendBadge(o)}
            <button class="add-btn compact" data-idx="${realIdx}">Ekle</button>
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
        `<span class="robot-alt">${escapeHtml(a.offer.marketLabel)} · ${money(a.offer.price)}</span>`
    )
    .join("");
  const idx = state.offers.findIndex(
    (x) => x.id === o.id || (x.title === o.title && x.marketId === o.marketId && x.price === o.price)
  );
  els.robotCard.hidden = false;
  els.robotCard.innerHTML = `
    <div class="robot-head">
      <span class="robot-badge">Kıyas robotu</span>
      <span class="robot-score">skor ${pick.score}</span>
    </div>
    <p class="robot-title">${escapeHtml(o.title)}</p>
    <p class="robot-summary">${escapeHtml(pick.summary || "")}</p>
    <ul class="robot-reasons">${reasons}</ul>
    <div class="robot-meta">
      <span class="market-badge"><i style="background:${o.marketColor || "#999"}"></i>${escapeHtml(o.marketLabel)}</span>
      <strong class="robot-price">${money(o.price)}</strong>
      ${o.volume ? `<span>${escapeHtml(o.volume)}</span>` : ""}
      <span>etiket ${pick.healthScore}/100</span>
      <span>fiyat ${pick.economyScore}/100</span>
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
  const btn = e.target.closest(".add-btn");
  if (!btn) return;
  const offer = state.offers[Number(btn.dataset.idx)];
  if (offer) addToCart(offer);
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
  const btn = e.target.closest(".qty-btn");
  if (!btn) return;
  changeQty(btn.dataset.market, btn.dataset.id, Number(btn.dataset.delta));
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
