@echo off
setlocal enabledelayedexpansion
title Cloudflare Named Tunnel - Lab Assistant
echo.
echo ========================================
echo    Cloudflare Named Tunnel
echo    (with Auto-Restart on Failure)
echo ========================================
echo.

:: Get script directory
set "SCRIPT_DIR=%~dp0"
set "DATA_DIR=%SCRIPT_DIR%data"
set "CONFIG_FILE=%USERPROFILE%\.cloudflared\config.yml"
set "METRICS_PORT=20241"

:: Check if cloudflared is installed
set "CLOUDFLARED_CMD="
where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
    set "CLOUDFLARED_CMD=cloudflared"
    goto :check_config
)

:: Check common install locations
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe" (
    set "CLOUDFLARED_CMD=%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe"
    goto :check_config
)

echo cloudflared not found.
echo.
echo Options:
echo   1. Run cloudflare-tunnel-setup.bat to install and configure
echo   2. Run cloudflare-quick-tunnel.bat for instant free access
echo.
pause
exit /b 1

:check_config
:: Check if named tunnel is configured
if not exist "%CONFIG_FILE%" (
    echo No named tunnel configured.
    echo.
    echo For a quick free tunnel (URL changes each restart), run:
    echo   cloudflare-quick-tunnel.bat
    echo.
    echo For a persistent URL, run:
    echo   cloudflare-tunnel-setup.bat
    echo.
    pause
    exit /b 1
)

:: Get tunnel info from config
set "TUNNEL_NAME="
set "HOSTNAME="

:: Read tunnel name from config
for /f "usebackq tokens=2" %%i in (`type "%CONFIG_FILE%" ^| findstr /i "^tunnel:"`) do set TUNNEL_NAME=%%i

:: Try to get hostname from tunnel_config.txt
if exist "%DATA_DIR%\tunnel_config.txt" (
    for /f "usebackq tokens=2 delims==" %%i in (`type "%DATA_DIR%\tunnel_config.txt" ^| findstr /i "^HOSTNAME="`) do set HOSTNAME=%%i
)

:: Show info
echo Named tunnel configuration found.
echo.
if not "!TUNNEL_NAME!"=="" echo   Tunnel:   !TUNNEL_NAME!
if not "!HOSTNAME!"=="" echo   URL:      https://!HOSTNAME!
echo   Config:   %CONFIG_FILE%
echo.
echo Features:
echo   - Health check every 10 seconds via /ready endpoint
echo   - Auto-restart when tunnel becomes unhealthy
echo   - Exponential backoff on repeated failures
echo.
echo NOTE: Keep this window open while using the tunnel.
echo       Close it or press Ctrl+C to stop.
echo.
echo ========================================
echo.

:: Run the named tunnel with health monitoring
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\start-named-tunnel.ps1" -CloudflaredPath "%CLOUDFLARED_CMD%" -TunnelName "!TUNNEL_NAME!" -MetricsPort %METRICS_PORT%

echo.
echo Tunnel stopped.
pause
