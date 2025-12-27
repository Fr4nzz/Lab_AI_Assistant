@echo off
setlocal enabledelayedexpansion
title Lab Assistant Launcher
echo.
echo ========================================
echo    Lab Assistant - Development Mode
echo ========================================
echo.

:: Parse command line arguments
set "START_TUNNEL="
set "NO_TUNNEL="

:parse_args
if "%~1"=="" goto :done_args
if /i "%~1"=="--tunnel" set "START_TUNNEL=1"
if /i "%~1"=="--no-tunnel" set "NO_TUNNEL=1"
shift
goto :parse_args
:done_args

:: Get network IPs with adapter type labels (Wi-Fi and Ethernet only)
set "NETWORK_IPS="
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "$ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '127.*' -and $_.InterfaceAlias -match 'Wi-Fi|Wireless|WLAN|Ethernet' -and $_.InterfaceAlias -notmatch 'VMware|VirtualBox|vEthernet|Hyper-V|WSL' }; foreach($ip in $ips) { if($ip.InterfaceAlias -match 'Wi-Fi|Wireless|WLAN') { Write-Host '[Wi-Fi]' $ip.IPAddress } else { Write-Host '[Ethernet]' $ip.IPAddress } }"`) do (
    if "!NETWORK_IPS!"=="" (
        set "NETWORK_IPS=%%i"
    ) else (
        set "NETWORK_IPS=!NETWORK_IPS!|%%i"
    )
)

:: Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

:: Check if Python is available
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found in PATH
    echo Please install Python and add it to PATH
    pause
    exit /b 1
)

:: Check if npm is available
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: npm not found in PATH
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

:: Install backend dependencies if needed
echo Checking backend dependencies...
cd /d "%SCRIPT_DIR%backend"
python -m pip install -r requirements.txt -q
cd /d "%SCRIPT_DIR%"

:: Install frontend dependencies if needed (check for essential packages)
set "NEED_INSTALL="
if not exist "%SCRIPT_DIR%frontend\node_modules\.bin\next.cmd" set "NEED_INSTALL=1"
if not exist "%SCRIPT_DIR%frontend\node_modules\@ducanh2912\next-pwa" set "NEED_INSTALL=1"
if not exist "%SCRIPT_DIR%frontend\node_modules\better-sqlite3" set "NEED_INSTALL=1"

if defined NEED_INSTALL (
    echo Installing frontend dependencies...
    cd /d "%SCRIPT_DIR%frontend"
    npm install --legacy-peer-deps
    cd /d "%SCRIPT_DIR%"
)

echo.
echo Starting Backend (Python FastAPI on port 8000)...
start "Lab Assistant - Backend" cmd /k "cd /d %SCRIPT_DIR%backend && python server.py"

:: Wait a moment for backend to start
timeout /t 3 /nobreak >nul

echo Starting Frontend (Next.js on port 3000)...
start "Lab Assistant - Frontend" cmd /k "cd /d %SCRIPT_DIR%frontend && npm run dev"

:: Wait for frontend to start
timeout /t 5 /nobreak >nul

:: Auto-open browser to the chat UI
echo Opening browser to http://localhost:3000...
start "" "http://localhost:3000"

rem Handle Cloudflare Tunnel
set "TUNNEL_URL="
set "TUNNEL_STARTED="

if not defined NO_TUNNEL (
    rem Check if cloudflared is available
    where cloudflared >nul 2>&1
    if not errorlevel 1 (
        rem Check if tunnel is configured
        if exist "%USERPROFILE%\.cloudflared\config.yml" (
            rem Get tunnel info
            for /f "tokens=2" %%i in ('findstr /i "tunnel:" "%USERPROFILE%\.cloudflared\config.yml"') do set TUNNEL_NAME=%%i
            for /f "tokens=1" %%i in ('cloudflared tunnel list 2^>nul ^| findstr /i "!TUNNEL_NAME!"') do set TUNNEL_ID=%%i

            if defined TUNNEL_ID (
                set "TUNNEL_URL=https://!TUNNEL_ID!.cfargotunnel.com"

                if defined START_TUNNEL (
                    echo.
                    echo Starting Cloudflare Tunnel...
                    start "Lab Assistant - Tunnel" cmd /k "cloudflared tunnel run !TUNNEL_NAME!"
                    set "TUNNEL_STARTED=1"
                ) else (
                    echo.
                    echo Cloudflare Tunnel is configured.
                    choice /c YN /m "Start tunnel for remote access"
                    if not errorlevel 2 (
                        echo Starting Cloudflare Tunnel...
                        start "Lab Assistant - Tunnel" cmd /k "cloudflared tunnel run !TUNNEL_NAME!"
                        set "TUNNEL_STARTED=1"
                    )
                )
            )
        ) else (
            if not defined START_TUNNEL (
                echo.
                echo [Info] Cloudflare Tunnel not configured.
                echo        Run cloudflare-tunnel-setup.bat to set up remote access.
            )
        )
    )
)

echo.
echo ========================================
echo    Lab Assistant Started!
echo ========================================
echo.
echo Local access:
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo.
echo Network access (LAN):
if not "!NETWORK_IPS!"=="" (
    for %%a in ("!NETWORK_IPS:|=" "!") do (
        for /f "tokens=1,2" %%b in (%%a) do (
            echo   %%b http://%%c:3000
        )
    )
) else (
    echo   [No Wi-Fi/Ethernet adapter found]
)

if defined TUNNEL_STARTED (
    echo.
    echo Remote access (Internet):
    echo   !TUNNEL_URL!
) else if defined TUNNEL_URL (
    echo.
    echo Remote access (not started):
    echo   !TUNNEL_URL!
    echo   Run with --tunnel flag or cloudflare-tunnel-run.bat
)

echo.
echo Opening browser...
start http://localhost:3000

echo.
echo Press any key to close this launcher...
echo (The backend, frontend, and tunnel will keep running)
pause >nul
