@echo off
title Quick Tunnel with WhatsApp Notification
echo.
echo ========================================
echo    Quick Tunnel + WhatsApp Notification
echo ========================================
echo.

:: Check if phone number provided
if "%~1"=="" (
    echo Usage: cloudflare-quick-tunnel-notify.bat +1234567890
    echo.
    echo Example:
    echo   cloudflare-quick-tunnel-notify.bat +51987654321
    echo.
    echo NOTE: You must be logged into WhatsApp Web in your browser first!
    echo.
    pause
    exit /b 1
)

:: Run Python script
python "%~dp0cloudflare-quick-tunnel-notify.py" %*
