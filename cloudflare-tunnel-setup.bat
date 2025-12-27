@echo off
setlocal enabledelayedexpansion
title Cloudflare Tunnel Setup
echo.
echo ========================================
echo    Cloudflare Tunnel - First Time Setup
echo ========================================
echo.

:: Check if cloudflared is installed
where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo cloudflared not found. Installing via winget...
    winget install Cloudflare.cloudflared
    if %errorlevel% neq 0 (
        echo.
        echo Failed to install. Please install manually:
        echo https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
        pause
        exit /b 1
    )
    echo.
    echo Installed successfully. Please restart this script.
    pause
    exit /b 0
)

echo cloudflared is installed.
echo.

:: Check if already logged in
if exist "%USERPROFILE%\.cloudflared\cert.pem" (
    echo Already logged in to Cloudflare.
) else (
    echo Step 1: Login to Cloudflare
    echo A browser window will open. Log in and authorize.
    echo.
    cloudflared tunnel login
    if %errorlevel% neq 0 (
        echo Login failed. Please try again.
        pause
        exit /b 1
    )
)

:: Set tunnel name
set TUNNEL_NAME=lab-assistant
set /p TUNNEL_NAME="Enter tunnel name (default: lab-assistant): "

:: Check if tunnel exists
cloudflared tunnel list | findstr /i "%TUNNEL_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo Tunnel '%TUNNEL_NAME%' already exists.
) else (
    echo.
    echo Step 2: Creating tunnel '%TUNNEL_NAME%'...
    cloudflared tunnel create %TUNNEL_NAME%
    if %errorlevel% neq 0 (
        echo Failed to create tunnel.
        pause
        exit /b 1
    )
)

:: Get tunnel ID
for /f "tokens=1" %%i in ('cloudflared tunnel list ^| findstr /i "%TUNNEL_NAME%"') do set TUNNEL_ID=%%i
echo Tunnel ID: %TUNNEL_ID%

:: Create config file
set CONFIG_DIR=%USERPROFILE%\.cloudflared
set CONFIG_FILE=%CONFIG_DIR%\config.yml

echo.
echo Step 3: Creating config file...
(
    echo tunnel: %TUNNEL_NAME%
    echo credentials-file: %CONFIG_DIR%\%TUNNEL_ID%.json
    echo.
    echo ingress:
    echo   - hostname: %TUNNEL_ID%.cfargotunnel.com
    echo     service: http://localhost:3000
    echo   - service: http_status:404
) > "%CONFIG_FILE%"

echo Config saved to: %CONFIG_FILE%
echo.
echo ========================================
echo    Setup Complete!
echo ========================================
echo.
echo Your permanent URL will be:
echo   https://%TUNNEL_ID%.cfargotunnel.com
echo.
echo To start the tunnel, run: cloudflare-tunnel-run.bat
echo To install as Windows service: cloudflare-tunnel-service.bat
echo.
pause
