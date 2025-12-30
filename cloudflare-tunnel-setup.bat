@echo off
setlocal enabledelayedexpansion
title Cloudflare Tunnel Setup
echo.
echo ========================================
echo    Cloudflare Tunnel - First Time Setup
echo ========================================
echo.

:: Check if cloudflared is installed (check PATH and common locations)
set "CLOUDFLARED_CMD="
where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
    set "CLOUDFLARED_CMD=cloudflared"
    goto :cloudflared_found
)

:: Check common install locations
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe" (
    set "CLOUDFLARED_CMD=%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe"
    goto :cloudflared_found
)
if exist "%ProgramFiles%\cloudflared\cloudflared.exe" (
    set "CLOUDFLARED_CMD=%ProgramFiles%\cloudflared\cloudflared.exe"
    goto :cloudflared_found
)

:: Not found - try to install
echo cloudflared not found. Installing via winget...
winget install Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements

:: Check again after install
where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
    set "CLOUDFLARED_CMD=cloudflared"
    goto :cloudflared_found
)
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe" (
    set "CLOUDFLARED_CMD=%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe"
    goto :cloudflared_found
)

:: Still not found - tell user to restart shell
echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo cloudflared was installed but your shell needs to reload PATH.
echo.
echo Please CLOSE this window and run the script again:
echo    .\cloudflare-tunnel-setup.bat
echo.
pause
exit /b 0

:cloudflared_found
echo cloudflared is installed.
echo.

:: Check if already logged in
if exist "%USERPROFILE%\.cloudflared\cert.pem" (
    echo Already logged in to Cloudflare.
) else (
    echo Step 1: Login to Cloudflare
    echo A browser window will open. Log in and authorize.
    echo.
    %CLOUDFLARED_CMD% tunnel login
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
%CLOUDFLARED_CMD% tunnel list | findstr /i "%TUNNEL_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo Tunnel '%TUNNEL_NAME%' already exists.
) else (
    echo.
    echo Step 2: Creating tunnel '%TUNNEL_NAME%'...
    %CLOUDFLARED_CMD% tunnel create %TUNNEL_NAME%
    if %errorlevel% neq 0 (
        echo Failed to create tunnel.
        pause
        exit /b 1
    )
)

:: Get tunnel ID
for /f "tokens=1" %%i in ('%CLOUDFLARED_CMD% tunnel list ^| findstr /i "%TUNNEL_NAME%"') do set TUNNEL_ID=%%i
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
