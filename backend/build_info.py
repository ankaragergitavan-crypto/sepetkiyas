"""Uygulama sürümü — Manual Deploy sonrası yüklü PWA bunu okuyup kendini yeniler."""

from __future__ import annotations

import os

# Her yayınında artırın (veya Render'da APP_BUILD env ile verin)
APP_BUILD = (os.getenv("APP_BUILD") or "25").strip()
APP_VERSION = (os.getenv("APP_VERSION") or "1.5.1").strip()


def build_payload() -> dict:
    return {
        "build": APP_BUILD,
        "version": APP_VERSION,
        "autoUpdate": True,
        "note": "Yüklü uygulama açılınca / öne gelince bu sürümü kontrol eder; sil-yükle gerekmez.",
    }
