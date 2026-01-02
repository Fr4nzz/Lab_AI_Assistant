@echo off
setlocal enabledelayedexpansion
title Cloudflare Quick Tunnel

:: Get script directory
set "SCRIPT_DIR=%~dp0"
set "DATA_DIR=%SCRIPT_DIR%data"
set "URL_FILE=%DATA_DIR%\tunnel_url.txt"

:: Create data directory if it doesn't exist
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"

echo:
echo ========================================
echo    Cloudflare Quick Tunnel
echo ========================================
echo:
echo This creates a FREE temporary public URL for your app.
echo The URL changes each time you restart this script.
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
echo Starting tunnel to http://localhost:3000...
echo:
echo Waiting for tunnel URL...
echo:

:: Clear old URL file
if exist "%URL_FILE%" del "%URL_FILE%"

:: Start tunnel and capture URL using PowerShell
:: This runs cloudflared and watches for the URL, saves it to file, then continues showing output
powershell -NoProfile -Command ^
    "$process = Start-Process -FilePath '%CLOUDFLARED_CMD%' -ArgumentList 'tunnel','--url','http://localhost:3000' -PassThru -NoNewWindow -RedirectStandardError '%TEMP%\cf_output.txt'; " ^
    "$found = $false; " ^
    "$timeout = 30; " ^
    "$elapsed = 0; " ^
    "while (-not $found -and -not $process.HasExited -and $elapsed -lt $timeout) { " ^
    "    Start-Sleep -Milliseconds 500; " ^
    "    $elapsed += 0.5; " ^
    "    if (Test-Path '%TEMP%\cf_output.txt') { " ^
    "        $content = Get-Content '%TEMP%\cf_output.txt' -Raw -ErrorAction SilentlyContinue; " ^
    "        if ($content -match 'https://[a-z0-9-]+\.trycloudflare\.com') { " ^
    "            $url = $matches[0]; " ^
    "            [System.IO.File]::WriteAllText('%URL_FILE%', $url); " ^
    "            Write-Host ''; " ^
    "            Write-Host '========================================'; " ^
    "            Write-Host '  TUNNEL URL SAVED!' -ForegroundColor Green; " ^
    "            Write-Host '========================================'; " ^
    "            Write-Host ''; " ^
    "            Write-Host \"  $url\" -ForegroundColor Cyan; " ^
    "            Write-Host ''; " ^
    "            Write-Host '  URL saved to: data\tunnel_url.txt'; " ^
    "            Write-Host '  Telegram bot will use this URL automatically.'; " ^
    "            Write-Host ''; " ^
    "            $found = $true; " ^
    "        } " ^
    "    } " ^
    "}; " ^
    "if (-not $found) { Write-Host 'Failed to get tunnel URL within 30s' -ForegroundColor Red }; " ^
    "Write-Host 'Tunnel is running. Press Ctrl+C to stop.' -ForegroundColor Yellow; " ^
    "Wait-Process -Id $process.Id"

:: Clean up temp file
if exist "%TEMP%\cf_output.txt" del "%TEMP%\cf_output.txt"

:: Clear URL file when tunnel stops
if exist "%URL_FILE%" del "%URL_FILE%"
echo:
echo Tunnel stopped.
pause
