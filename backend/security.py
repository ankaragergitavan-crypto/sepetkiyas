"""Erişim duvarı + güvenlik başlıkları + gizlilik ayarları."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response as StarletteResponse

# ---- Yapılandırma (Render Environment) ----
# ACCESS_PIN: uygulamaya giriş şifresi (zorunlu önerilir)
# ALLOWED_IPS: virgülle IP listesi; boşsa IP kilidi yok
# ALLOWED_ORIGINS: CORS; boşsa sadece kendi host
# STRICT_PRIVACY=1: telefon verisi dışarı minimal; OFF/Getir ek çağrı kapalı
# SESSION_DAYS: oturum süresi

ACCESS_PIN = (os.getenv("ACCESS_PIN") or os.getenv("APP_PIN") or "agt-kilit").strip()
# Boş bırakmak için: ACCESS_PIN=off
if ACCESS_PIN.lower() in {"off", "none", "0", "false"}:
    ACCESS_PIN = ""
ALLOWED_IPS = {
    x.strip()
    for x in (os.getenv("ALLOWED_IPS") or "").split(",")
    if x.strip()
}
_raw_origins = (os.getenv("ALLOWED_ORIGINS") or "").strip()
ALLOWED_ORIGINS = {x.strip().rstrip("/") for x in _raw_origins.split(",") if x.strip()}
STRICT_PRIVACY = (os.getenv("STRICT_PRIVACY") or "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SESSION_DAYS = max(1, int(os.getenv("SESSION_DAYS") or "30"))
COOKIE_NAME = "agt_gate"
_SECRET = (os.getenv("GATE_SECRET") or ACCESS_PIN or secrets.token_hex(16)).encode("utf-8")

# Sağlık / statik / giriş dışındaki her şey kilitli (PIN varsa)
_PUBLIC_PATHS = {
    "/api/health",
    "/api/auth/status",
    "/api/auth/unlock",
    "/sw.js",
    "/manifest.webmanifest",
    "/robots.txt",
    "/favicon.ico",
}


def gate_enabled() -> bool:
    return bool(ACCESS_PIN)


def privacy_payload() -> dict:
    return {
        "gateEnabled": gate_enabled(),
        "strictPrivacy": STRICT_PRIVACY,
        "ipAllowlist": bool(ALLOWED_IPS),
        "note": (
            "Sepet ve fiyat geçmişi yalnızca bu cihazda (localStorage). "
            "Konum ham GPS olarak sunucuya gitmez; yalnızca seçilen ilçe koordinatı kullanılır. "
            "Canlı fiyat için yalnızca market fiyat kaynağına ürün araması gider. "
            "Telefonunuza dışarıdan bağlantı açılmaz (PWA sunucu istemez)."
        ),
    }


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    if request.client:
        return request.client.host or ""
    return ""


def ip_allowed(request: Request) -> bool:
    if not ALLOWED_IPS:
        return True
    ip = _client_ip(request)
    return ip in ALLOWED_IPS


def _token_for_pin(pin: str, issued: int) -> str:
    msg = f"{pin}:{issued}".encode("utf-8")
    return hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()


def make_session_cookie_value(pin: str) -> str:
    issued = int(time.time())
    sig = _token_for_pin(pin, issued)
    return f"{issued}.{sig}"


def session_valid(cookie: str | None, pin: str) -> bool:
    if not cookie or not pin:
        return False
    try:
        issued_s, sig = cookie.split(".", 1)
        issued = int(issued_s)
    except (ValueError, AttributeError):
        return False
    max_age = SESSION_DAYS * 86400
    if issued < time.time() - max_age or issued > time.time() + 300:
        return False
    expected = _token_for_pin(pin, issued)
    return hmac.compare_digest(expected, sig)


def unlock_ok(pin: str) -> bool:
    if not ACCESS_PIN:
        return True
    return hmac.compare_digest(pin.strip(), ACCESS_PIN)


def request_authorized(request: Request) -> bool:
    if not gate_enabled():
        return True
    return session_valid(request.cookies.get(COOKIE_NAME), ACCESS_PIN)


def security_headers(response: StarletteResponse, *, request: Request | None = None) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = (
        "geolocation=(self), camera=(self), microphone=(), "
        "payment=(), usb=(), interest-cohort=()"
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    # Canlı fiyat + (opsiyonel) OFF; harici izleme yok
    csp = (
        "default-src 'self'; "
        "img-src 'self' data: https: blob:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "connect-src 'self' https://api.marketfiyati.org.tr "
        "https://world.openfoodfacts.org https://unpkg.com "
        "https://locals-web-api-gateway.artisan.getirapi.com "
        "https://api.reefapi.com; "
        "worker-src 'self' blob:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    if STRICT_PRIVACY:
        csp = (
            "default-src 'self'; "
            "img-src 'self' data: https: blob:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "connect-src 'self' https://api.marketfiyati.org.tr https://unpkg.com; "
            "worker-src 'self' blob:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-AGT-Privacy"] = "device-local-carts;no-phone-inbound"


class SecurityFirewallMiddleware(BaseHTTPMiddleware):
    """IP allowlist + PIN kapısı + güvenlik başlıkları."""

    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        path = request.url.path

        if not ip_allowed(request):
            return JSONResponse(
                {
                    "detail": "Erişim engellendi (IP güvenlik duvarı).",
                    "code": "ip_blocked",
                },
                status_code=403,
            )

        # Statik ve public yollar
        public = (
            path in _PUBLIC_PATHS
            or path.startswith("/static/")
            or path == "/"
            or path.startswith("/icons/")
        )

        if gate_enabled() and not public and not request_authorized(request):
            if path.startswith("/api/"):
                return JSONResponse(
                    {
                        "detail": "Giriş gerekli. ACCESS_PIN ile kilidi açın.",
                        "code": "auth_required",
                        "privacy": privacy_payload(),
                    },
                    status_code=401,
                )
            # HTML sayfası: yine de index dönsün; JS kilit ekranı göstersin
            # (index public)

        response = await call_next(request)
        security_headers(response, request=request)
        return response


def cors_origins_for_starlette() -> list[str]:
    if ALLOWED_ORIGINS:
        return sorted(ALLOWED_ORIGINS)
    # Varsayılan: tarayıcı same-origin; wildcard yok (dış siteler API çağırmaz)
    return []
