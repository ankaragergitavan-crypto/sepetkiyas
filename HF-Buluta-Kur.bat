@echo off
chcp 65001 >nul
title SepetKiyas HuggingFace Spaces
cd /d "%~dp0"

echo Hugging Face girisi (tarayici/token)...
python -m huggingface_hub.commands.huggingface_cli login
if errorlevel 1 (
  echo Giris basarisiz. https://huggingface.co/settings/tokens adresinden token al.
  pause
  exit /b 1
)

echo Space olusturuluyor ve yukleniyor...
python scripts\deploy_hf_space.py
pause
