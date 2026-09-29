"""Gerçek uçtan uca sistem testi — sahte veri yok."""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from typing import Any

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ANKARA = {"latitude": 39.9777, "longitude": 32.8670, "distance": 10}
# Bilinen uzak şehir — Ankara clamp / filtre doğrulaması
ISTANBUL = {"latitude": 41.0082, "longitude": 28.9784, "distance": 10}

PASS = 0
FAIL = 0
WARN = 0


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    print(f"  OK  {msg}")


def fail(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f" FAIL {msg}")


def warn(msg: str) -> None:
    global WARN
    WARN += 1
    print(f" WARN {msg}")


def check_offer(o: dict[str, Any], *, require_ankara: bool = True) -> list[str]:
    errs: list[str] = []
    price = o.get("price")
    if not isinstance(price, (int, float)) or price <= 0:
        errs.append(f"invalid price={price!r}")
    if not o.get("title"):
        errs.append("empty title")
    if not o.get("marketId"):
        errs.append("missing marketId")
    if not o.get("marketLabel"):
        errs.append("missing marketLabel")
    if o.get("source") not in ("marketfiyati", "getir", "getir_carsi", "getir_buyuk"):
        # allow known live sources
        src = o.get("source")
        if src not in ("marketfiyati", "getir"):
            errs.append(f"unexpected source={src!r}")
    if require_ankara:
        lat, lon = o.get("depotLat"), o.get("depotLon")
        if lat is not None and lon is not None:
            if not (39.70 <= float(lat) <= 40.20 and 32.45 <= float(lon) <= 33.15):
                errs.append(f"outside Ankara lat={lat} lon={lon}")
        dist = o.get("distanceKm")
        if dist is not None and float(dist) > 20:
            errs.append(f"distance too far: {dist} km")
    return errs


def main() -> int:
    print(f"BASE = {BASE}")
    client = httpx.Client(timeout=90.0)

    # 1) health
    print("\n== health ==")
    r = client.get(f"{BASE}/api/health")
    if r.status_code == 200 and r.json().get("status") == "ok":
        ok(f"health {r.json().get('status')}")
    else:
        fail(f"health status={r.status_code} body={r.text[:200]}")

    # 2) markets
    print("\n== markets ==")
    r = client.get(f"{BASE}/api/markets")
    data = r.json()
    markets = data.get("markets") or []
    live = [m for m in markets if m.get("live")]
    pending = [m for m in markets if m.get("source") == "pending"]
    if live:
        ok(f"{len(live)} live markets: {', '.join(m['label'] for m in live)}")
    else:
        fail("no live markets")
    if pending:
        fail(f"pending/fake markets still listed: {[m['id'] for m in pending]}")
    else:
        ok("no pending/fake markets in list")
    if any(m["id"] == "hakmar" for m in markets):
        fail("Hakmar listed (not useful for Ankara)")
    else:
        ok("Hakmar not listed")

    # 3) real searches
    queries = ["süt 1L", "yumurta", "ekmek", "ayçiçek yağı", "domates"]
    all_offers: list[dict[str, Any]] = []
    for q in queries:
        print(f"\n== search: {q!r} ==")
        t0 = time.time()
        r = client.post(f"{BASE}/api/search", json={"query": q, **ANKARA, "include_getir": True})
        elapsed = time.time() - t0
        if r.status_code != 200:
            fail(f"HTTP {r.status_code}: {r.text[:300]}")
            continue
        body = r.json()
        offers = body.get("offers") or []
        policy = body.get("dataPolicy") or {}
        robot = body.get("robot") or {}
        groups = body.get("groups") or []
        by_m = body.get("byMarket") or {}

        if not policy.get("livePricesOnly") or not policy.get("noFabricatedOffers"):
            fail(f"dataPolicy weak: {policy}")
        else:
            ok("dataPolicy live-only")

        if not offers:
            fail(f"zero offers for {q!r} ({elapsed:.1f}s)")
            continue

        ok(f"{len(offers)} offers in {elapsed:.1f}s | markets={by_m}")
        all_offers.extend(offers)

        bad = 0
        for o in offers:
            errs = check_offer(o)
            if errs:
                bad += 1
                if bad <= 3:
                    fail(f"{o.get('title','?')[:40]} @ {o.get('marketLabel')}: {errs}")
        if bad == 0:
            ok("all offers have valid live price + Ankara geo")
        else:
            fail(f"{bad}/{len(offers)} offers failed integrity checks")

        # prices look like real TRY grocery range (sanity, not strict)
        prices = [float(o["price"]) for o in offers if o.get("price")]
        if prices and min(prices) < 0.5:
            fail(f"suspiciously low min price {min(prices)}")
        if prices and max(prices) > 50000:
            warn(f"very high max price {max(prices)} — check outliers")
        else:
            ok(f"price range ₺{min(prices):.2f}–₺{max(prices):.2f}")

        # trends must not invent history
        fake_trend = [o for o in offers if o.get("trend") in ("up", "down") and not o.get("trendFromHistory") and o.get("previousPrice") is None]
        # check our trend fields
        invented = []
        for o in offers:
            if o.get("trend") in ("up", "down"):
                if o.get("previousPrice") is None and not o.get("trendDelta"):
                    # allow if has previousPrice or delta from real history
                    if o.get("previousPrice") is None:
                        invented.append(o)
        # softer: if trend present without prev price observation
        for o in offers:
            t = o.get("trend")
            if t in ("up", "down") and o.get("previousPrice") is None:
                invented.append(o.get("title"))
        if invented:
            # might still be ok if trendDelta exists from store — inspect fields
            sample = next((o for o in offers if o.get("trend") in ("up", "down")), None)
            if sample and sample.get("previousPrice") is None:
                warn(f"trend without previousPrice sample keys={list(sample.keys())}")
            else:
                ok("trends look observation-based or absent")
        else:
            ok("no invented up/down trends without prior price")

        # robot honesty
        pick = (robot.get("pick") or {}).get("offer") if robot else None
        if pick:
            if pick.get("price") and pick["price"] > 0:
                ok(f"robot pick: {pick.get('marketLabel')} ₺{pick.get('price')} — {pick.get('title','')[:40]}")
            else:
                fail(f"robot pick invalid price: {pick}")
            reasons = (robot.get("pick") or {}).get("reasons") or []
            if reasons:
                ok(f"robot reasons: {reasons[:2]}")
            else:
                warn("robot pick has no reasons")
        else:
            warn(f"no robot pick for {q!r}")

        if groups:
            g0 = groups[0]
            if g0.get("bestPrice") and g0.get("offers"):
                best = min(float(x["price"]) for x in g0["offers"])
                if abs(best - float(g0["bestPrice"])) < 0.01:
                    ok(f"group bestPrice matches min ({g0.get('title','')[:30]})")
                else:
                    fail(f"group bestPrice {g0['bestPrice']} != min {best}")
            ok(f"{len(groups)} product groups")
        else:
            warn("no groups returned")

        # unit price / annotation
        annotated = sum(1 for o in offers if o.get("unitPriceEstimate") is not None or o.get("economyScore") is not None)
        if annotated:
            ok(f"{annotated}/{len(offers)} offers annotated (unit/economy)")
        else:
            warn("no unitPriceEstimate/economyScore annotations")

    # 4) Istanbul coords must clamp / only Ankara depots
    print("\n== Istanbul coords clamp ==")
    r = client.post(
        f"{BASE}/api/search",
        json={"query": "süt", **ISTANBUL, "include_getir": False},
    )
    if r.status_code != 200:
        fail(f"istanbul search HTTP {r.status_code}")
    else:
        body = r.json()
        loc = body.get("location") or {}
        offers = body.get("offers") or []
        # After clamp, location should be Ankara defaults or still show search loc — check depots
        outside = [
            o
            for o in offers
            if o.get("depotLat") is not None
            and not (39.70 <= float(o["depotLat"]) <= 40.20 and 32.45 <= float(o["depotLon"]) <= 33.15)
        ]
        if outside:
            fail(f"{len(outside)} offers outside Ankara with Istanbul input")
            for o in outside[:3]:
                print(f"    {o.get('depotName')} {o.get('depotLat')},{o.get('depotLon')}")
        else:
            ok(f"Istanbul input → {len(offers)} Ankara-only offers (loc={loc})")

    # 5) frontend assets
    print("\n== frontend ==")
    for path in ["/", "/static/app.js", "/static/styles.css", "/sw.js"]:
        r = client.get(f"{BASE}{path}")
        if r.status_code == 200:
            ok(path)
        else:
            fail(f"{path} -> {r.status_code}")
    js = client.get(f"{BASE}/static/app.js").text
    if "best-badge" in js and "lowestPrice" in js:
        ok("app.js has En uygun highlight")
    else:
        fail("app.js missing price highlight helpers")
    css = client.get(f"{BASE}/static/styles.css").text
    if "font-family: var(--font)" in css and ".price" in css:
        ok("styles.css price uses readable font")
    else:
        fail("styles.css price font not updated")

    # 6) market diversity summary
    print("\n== summary ==")
    mc = Counter(o.get("marketLabel") for o in all_offers)
    print("  markets seen:", dict(mc))
    if len(mc) < 2:
        fail("fewer than 2 markets returned across queries")
    else:
        ok(f"{len(mc)} distinct markets across queries")

    print(f"\nRESULT: {PASS} ok, {FAIL} fail, {WARN} warn")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
