@echo off
setlocal enabledelayedexpansion
title Cloudflare Tunnel - Lab Assistant
echo.
echo ========================================
echo    Cloudflare Tunnel
echo ========================================
echo.

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
if not exist "%USERPROFILE%\.cloudflared\config.yml" (
    echo No named tunnel configured.
    echo.
    echo For a quick free tunnel (URL changes each restart^), run:
    echo   cloudflare-quick-tunnel.bat
    echo.
    echo For a persistent URL, you need a domain. Run:
    echo   cloudflare-tunnel-setup.bat
    echo.
    pause
    exit /b 1
)

:: Named tunnel exists - run it
echo Named tunnel configuration found.
echo.

:: Try to get tunnel info (may fail if config has issues)
set "TUNNEL_NAME="
for /f "usebackq tokens=2" %%i in (`type "%USERPROFILE%\.cloudflared\config.yml" ^| findstr /i "^tunnel:"`) do set TUNNEL_NAME=%%i

if "!TUNNEL_NAME!"=="" (
    echo Warning: Could not read tunnel name from config.
    echo Running tunnel with config file...
    echo.
    %CLOUDFLARED_CMD% tunnel run
) else (
    echo Tunnel: !TUNNEL_NAME!
    echo.
    echo Starting tunnel... Press Ctrl+C to stop.
    echo.
    %CLOUDFLARED_CMD% tunnel run !TUNNEL_NAME!
)
