@echo off
REM CryptoHelper 自動掃描器
REM 每15分鐘執行一次掃描

cd /d D:\CryptoHelper
python -m src.main --single-run

REM 如果有錯誤，將錯誤訊息輸出到 logs.txt
if errorlevel 1 (
    echo [%date% %time%] Scanner encountered an error >> logs.txt
)
