@echo off
title Cloudflare Quick Tunnel
echo.
echo ========================================
echo    Cloudflare Quick Tunnel
echo ========================================
echo.
echo This creates a FREE temporary public URL for your app.
echo The URL changes each time you restart this script.
echo.
echo NOTE: Keep this window open while using the tunnel.
echo       Close it to stop the tunnel.
echo.
echo ========================================
echo.

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

echo.
echo cloudflared installed but PATH needs refresh.
echo Please close this window and run again.
pause
exit /b 0

:run_tunnel
echo Starting tunnel to http://localhost:3000...
echo.
echo Your public URL will appear below (look for "trycloudflare.com"):
echo.
%CLOUDFLARED_CMD% tunnel --url http://localhost:3000
