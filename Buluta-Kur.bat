@echo off
chcp 65001 >nul
title SepetKiyas Bulut Kurulum
cd /d "%~dp0"

set FLY=%~dp0tools\flyctl.exe
if not exist "%FLY%" (
  echo flyctl bulunamadi. tools\flyctl.exe eksik.
  pause
  exit /b 1
)

echo ========================================
echo  SepetKiyas kalici bulut kurulumu
echo  Fly.io hesabinla tarayicide giris yap
echo ========================================
echo.

"%FLY%" auth login
if errorlevel 1 (
  echo Giris basarisiz.
  pause
  exit /b 1
)

echo.
echo Yayin basliyor...
"%FLY%" launch --name sepetkiyas --region fra --yes --copy-config --no-deploy
"%FLY%" deploy --ha=false

echo.
echo --- SONUC ---
"%FLY%" status
echo.
echo Public link genellikle: https://sepetkiyas.fly.dev
"%FLY%" apps list
pause
