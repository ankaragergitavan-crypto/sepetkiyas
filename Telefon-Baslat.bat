@echo off
chcp 65001 >nul
title SepetKiyas Telefon
cd /d "%~dp0"

set PATH=%PATH%;C:\Program Files\Git\cmd;C:\Program Files (x86)\cloudflared

echo [1/2] Sunucu baslatiliyor...
start "SepetKiyas-Server" cmd /c "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo [2/2] Telefon linki olusturuluyor (Cloudflare)...
echo.
echo Asagidaki https://....trycloudflare.com adresini telefona yaz.
echo PC kapaninca veya bu pencere kapaninca link de kapanir.
echo.
cloudflared tunnel --url http://127.0.0.1:8000
pause
