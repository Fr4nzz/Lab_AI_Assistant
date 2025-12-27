@echo off
title Cloudflare Tunnel - Lab Assistant
echo.
echo ========================================
echo    Cloudflare Tunnel
echo ========================================
echo.

:: Check if cloudflared is installed
where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: cloudflared not found.
    echo Please run cloudflare-tunnel-setup.bat first.
    pause
    exit /b 1
)

:: Check if config exists
if not exist "%USERPROFILE%\.cloudflared\config.yml" (
    echo Error: Tunnel not configured.
    echo Please run cloudflare-tunnel-setup.bat first.
    pause
    exit /b 1
)

:: Extract tunnel name from config
for /f "tokens=2" %%i in ('findstr /i "tunnel:" "%USERPROFILE%\.cloudflared\config.yml"') do set TUNNEL_NAME=%%i

:: Get tunnel ID
for /f "tokens=1" %%i in ('cloudflared tunnel list ^| findstr /i "%TUNNEL_NAME%"') do set TUNNEL_ID=%%i

echo Tunnel URL: https://%TUNNEL_ID%.cfargotunnel.com
echo.
echo Starting tunnel... Press Ctrl+C to stop.
echo.

cloudflared tunnel run %TUNNEL_NAME%
