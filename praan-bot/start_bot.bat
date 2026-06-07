@echo off
title PRAAN Veeru Bot
echo ==========================================
echo   PRAAN Blood Warriors — Veeru Telegram Bot
echo ==========================================
echo.

REM Check backend is reachable
curl -s http://localhost:8000/stats >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Backend at localhost:8000 is NOT reachable.
    echo           Make sure the PRAAN backend is running first.
    echo           Press any key to start the bot anyway...
    pause >nul
) else (
    echo [OK] Backend at localhost:8000 is reachable.
)

echo.
echo Starting Veeru bot...
echo Press Ctrl+C to stop.
echo.

py -3 bot.py

echo.
echo Bot stopped. Press any key to exit.
pause >nul
