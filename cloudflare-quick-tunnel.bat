@echo off
setlocal enabledelayedexpansion
title Cloudflare Quick Tunnel (with Health Check)

:: Get script directory
set "SCRIPT_DIR=%~dp0"
set "DATA_DIR=%SCRIPT_DIR%data"
set "URL_FILE=%DATA_DIR%\tunnel_url.txt"
set "METRICS_PORT=20241"

:: Create data directory if it doesn't exist
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"

echo:
echo ========================================
echo    Cloudflare Quick Tunnel
echo    (with Auto-Restart on Failure)
echo ========================================
echo:
echo This creates a FREE temporary public URL for your app.
echo The URL changes each time you restart this script.
echo:
echo Features:
echo   - Health check every 10 seconds via /ready endpoint
echo   - Auto-restart when tunnel becomes unhealthy
echo   - Exponential backoff on repeated failures
echo:
echo NOTE: Keep this window open while using the tunnel.
echo       Close it to stop the tunnel.
echo:
echo ========================================
echo:

:: Check if cloudflared is installed
set "CLOUDFLARED_CMD="
where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
    set "CLOUDFLARED_CMD=cloudflared"
    goto :run_tunnel
)

:: Check common install locations
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe" (
    set "CLOUDFLARED_CMD=%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe"
    goto :run_tunnel
)

:: Not found - install it
echo cloudflared not found. Installing...
winget install Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements

:: Check again
where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
    set "CLOUDFLARED_CMD=cloudflared"
    goto :run_tunnel
)
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe" (
    set "CLOUDFLARED_CMD=%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe"
    goto :run_tunnel
)

echo:
echo cloudflared installed but PATH needs refresh.
echo Please close this window and run again.
pause
exit /b 0

:run_tunnel
:: Use the PowerShell script for proper health monitoring
echo Starting tunnel with health monitoring...
echo:

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\start-tunnel.ps1" -CloudflaredPath "%CLOUDFLARED_CMD%" -Port 3000 -MetricsPort %METRICS_PORT%

echo:
echo Tunnel stopped.
pause
