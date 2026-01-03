@echo off
setlocal enabledelayedexpansion
title Cloudflare Named Tunnel Setup
echo.
echo ========================================
echo    Cloudflare Named Tunnel Setup
echo ========================================
echo.
echo This will set up a PERMANENT tunnel URL for your Lab Assistant.
echo.
echo Prerequisites:
echo   - A Cloudflare account (free)
echo   - A domain added to Cloudflare (any registrar works)
echo.
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
echo Please CLOSE this window and run the script again.
echo.
pause
exit /b 0

:cloudflared_found
echo [OK] cloudflared is installed.
echo.

:: ========================================
:: Step 1: Login to Cloudflare
:: ========================================
if exist "%USERPROFILE%\.cloudflared\cert.pem" (
    echo [OK] Already logged in to Cloudflare.
    echo.
) else (
    echo ----------------------------------------
    echo Step 1: Login to Cloudflare
    echo ----------------------------------------
    echo.
    echo A browser window will open.
    echo   1. Log in to your Cloudflare account
    echo   2. Select the domain you want to use
    echo   3. Authorize the connection
    echo.
    pause
    echo.
    %CLOUDFLARED_CMD% tunnel login
    if %errorlevel% neq 0 (
        echo.
        echo Login failed. Please try again.
        pause
        exit /b 1
    )
    echo.
    echo [OK] Login successful!
    echo.
)

:: ========================================
:: Step 2: Create Tunnel
:: ========================================
echo ----------------------------------------
echo Step 2: Create Tunnel
echo ----------------------------------------
echo.

set "TUNNEL_NAME=lab-assistant"
set /p TUNNEL_NAME="Tunnel name (default: lab-assistant): "

:: Check if tunnel exists
%CLOUDFLARED_CMD% tunnel list 2>nul | findstr /i "!TUNNEL_NAME!" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Tunnel '!TUNNEL_NAME!' already exists.
) else (
    echo Creating tunnel '!TUNNEL_NAME!'...
    %CLOUDFLARED_CMD% tunnel create !TUNNEL_NAME!
    if %errorlevel% neq 0 (
        echo.
        echo Failed to create tunnel.
        pause
        exit /b 1
    )
    echo [OK] Tunnel created!
)
echo.

:: Get tunnel ID
set "TUNNEL_ID="
for /f "tokens=1" %%i in ('%CLOUDFLARED_CMD% tunnel list 2^>nul ^| findstr /i "!TUNNEL_NAME!"') do set TUNNEL_ID=%%i

if "!TUNNEL_ID!"=="" (
    echo Error: Could not get tunnel ID.
    pause
    exit /b 1
)
echo Tunnel ID: !TUNNEL_ID!
echo.

:: ========================================
:: Step 3: Configure Hostname
:: ========================================
echo ----------------------------------------
echo Step 3: Configure Hostname
echo ----------------------------------------
echo.
echo Enter the full hostname for your tunnel.
echo Example: lab.yourdomain.com
echo.
echo This must be a subdomain of a domain in your Cloudflare account.
echo.

set "HOSTNAME="
set /p HOSTNAME="Hostname (e.g., lab.yourdomain.com): "

if "!HOSTNAME!"=="" (
    echo Error: Hostname is required.
    pause
    exit /b 1
)

:: ========================================
:: Step 4: Create DNS Record
:: ========================================
echo.
echo ----------------------------------------
echo Step 4: Create DNS Record
echo ----------------------------------------
echo.
echo Creating DNS record for !HOSTNAME!...
echo.

%CLOUDFLARED_CMD% tunnel route dns !TUNNEL_NAME! !HOSTNAME!
if %errorlevel% neq 0 (
    echo.
    echo Warning: DNS record creation may have failed.
    echo You can create it manually in Cloudflare dashboard:
    echo   Type: CNAME
    echo   Name: !HOSTNAME!
    echo   Target: !TUNNEL_ID!.cfargotunnel.com
    echo.
    pause
) else (
    echo [OK] DNS record created!
)
echo.

:: ========================================
:: Step 5: Create Config File
:: ========================================
echo ----------------------------------------
echo Step 5: Create Configuration
echo ----------------------------------------
echo.

set "CONFIG_DIR=%USERPROFILE%\.cloudflared"
set "CONFIG_FILE=!CONFIG_DIR!\config.yml"
set "CREDS_FILE=!CONFIG_DIR!\!TUNNEL_ID!.json"

:: Create config file
(
    echo # Cloudflare Tunnel Configuration
    echo # Generated by Lab Assistant setup
    echo.
    echo tunnel: !TUNNEL_NAME!
    echo credentials-file: !CREDS_FILE!
    echo.
    echo # Metrics endpoint for health monitoring
    echo metrics: 127.0.0.1:20241
    echo.
    echo ingress:
    echo   # Lab Assistant frontend
    echo   - hostname: !HOSTNAME!
    echo     service: http://localhost:3000
    echo   # Catch-all rule ^(required^)
    echo   - service: http_status:404
) > "!CONFIG_FILE!"

echo [OK] Config saved to: !CONFIG_FILE!
echo.

:: ========================================
:: Step 6: Save tunnel info for scripts
:: ========================================
set "DATA_DIR=%~dp0data"
if not exist "!DATA_DIR!" mkdir "!DATA_DIR!"

:: Save tunnel info
(
    echo TUNNEL_NAME=!TUNNEL_NAME!
    echo TUNNEL_ID=!TUNNEL_ID!
    echo HOSTNAME=!HOSTNAME!
) > "!DATA_DIR!\tunnel_config.txt"

:: Save the permanent URL
echo https://!HOSTNAME!> "!DATA_DIR!\tunnel_url.txt"

echo.
echo ========================================
echo    Setup Complete!
echo ========================================
echo.
echo Your PERMANENT tunnel URL is:
echo.
echo    https://!HOSTNAME!
echo.
echo ----------------------------------------
echo.
echo Next steps:
echo.
echo   1. TEST the tunnel:
echo      .\cloudflare-tunnel-run.bat
echo.
echo   2. INSTALL as Windows service (auto-start):
echo      .\cloudflare-tunnel-service.bat
echo      (Run as Administrator)
echo.
echo ----------------------------------------
echo.
echo Documentation: docs\cloudflare-named-tunnel-setup.md
echo.
pause
