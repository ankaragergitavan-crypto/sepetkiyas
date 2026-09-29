@echo off
chcp 65001 >nul
title SepetKiyas
cd /d "%~dp0"

echo SepetKiyas baslatiliyor...
where python >nul 2>&1
if errorlevel 1 (
  echo Python bulunamadi. Lutfen Python kurun.
  pause
  exit /b 1
)

start "" "http://127.0.0.1:8000"

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
if errorlevel 1 (
  echo Sunucu kapanadi veya baslamadi.
  pause
)
