@echo off
chcp 65001 >nul
title CryptoHelper Scanner - 運行中...

cls
echo ═══════════════════════════════════════
echo   🚀 CryptoHelper 加密貨幣掃描器
echo ═══════════════════════════════════════
echo.
echo ✅ Scanner 正在啟動...
echo 📊 每 15 分鐘自動掃描幣安期貨
echo 💬 有訊號時自動發送 Telegram 通知
echo.
echo ⚠️  關閉此視窗將停止掃描
echo ═══════════════════════════════════════
echo.

cd /d "%~dp0"
python -m src.main

echo.
echo ═══════════════════════════════════════
echo   掃描器已停止
echo ═══════════════════════════════════════
pause
