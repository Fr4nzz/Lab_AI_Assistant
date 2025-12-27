@echo off
title Cloudflare Tunnel - Service Install
echo.
echo ========================================
echo    Cloudflare Tunnel - Service Install
echo ========================================
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo This requires Administrator privileges.
    echo Right-click and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

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

echo Installing Cloudflare Tunnel as Windows Service...
echo.

cloudflared service install

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo    Service Installed Successfully!
    echo ========================================
    echo.
    echo The tunnel will now start automatically with Windows.
    echo.
    echo To manage the service:
    echo   Start:   net start cloudflared
    echo   Stop:    net stop cloudflared
    echo   Remove:  cloudflared service uninstall
    echo.
) else (
    echo.
    echo Failed to install service.
    echo.
)

pause
