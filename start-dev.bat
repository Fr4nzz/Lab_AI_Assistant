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
set "RESTART_MODE="

:parse_args
if "%~1"=="" goto :done_args
if /i "%~1"=="--tunnel" set "START_TUNNEL=1"
if /i "%~1"=="--no-tunnel" set "NO_TUNNEL=1"
if /i "%~1"=="--restart" set "RESTART_MODE=1"
shift
goto :parse_args
:done_args

:: Kill existing processes on ports 8000, 3000, and 24678 (for restart/update scenarios)
echo Checking for existing processes...

:: Kill existing terminal windows by title using PowerShell (most reliable method)
:: This finds cmd.exe windows with "Lab Assistant" in title and closes them
powershell -NoProfile -Command "Get-Process | Where-Object { $_.ProcessName -eq 'cmd' -and $_.MainWindowTitle -like '*Lab Assistant*' } | ForEach-Object { $_.CloseMainWindow() | Out-Null; Start-Sleep -Milliseconds 100; if (!$_.HasExited) { $_.Kill() } }" 2>nul

:: Also kill any Python/Node processes on our ports
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 24678 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

:: Delay to ensure windows close and ports are released
timeout /t 2 /nobreak >nul

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

:: Load environment variables from root .env file
if exist "%SCRIPT_DIR%.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%SCRIPT_DIR%.env") do (
        :: Skip comments and empty lines
        set "LINE=%%a"
        if not "!LINE:~0,1!"=="#" if not "!LINE!"=="" (
            set "%%a=%%b"
        )
    )
)

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
if not exist "%SCRIPT_DIR%frontend-nuxt\node_modules\.bin\nuxt.cmd" set "NEED_INSTALL=1"
if not exist "%SCRIPT_DIR%frontend-nuxt\node_modules\@nuxt\ui" set "NEED_INSTALL=1"
if not exist "%SCRIPT_DIR%frontend-nuxt\node_modules\better-sqlite3" set "NEED_INSTALL=1"
if not exist "%SCRIPT_DIR%frontend-nuxt\node_modules\sharp" set "NEED_INSTALL=1"

if defined NEED_INSTALL (
    echo Installing frontend dependencies...
    cd /d "%SCRIPT_DIR%frontend-nuxt"
    call npm install
    cd /d "%SCRIPT_DIR%"
)

echo.
echo Starting Backend (Python FastAPI on port 8000)...
start "Lab Assistant - Backend" cmd /k "cd /d %SCRIPT_DIR%backend && python server.py"

:: Wait a moment for backend to start
timeout /t 3 /nobreak >nul

echo Starting Frontend (Nuxt on port 3000)...
start "Lab Assistant - Frontend" cmd /k "cd /d %SCRIPT_DIR%frontend-nuxt && npm run dev"

:: Wait for frontend to start
timeout /t 5 /nobreak >nul

:: Auto-open browser to the chat UI (skip in restart mode)
if not defined RESTART_MODE (
    echo Opening browser to http://localhost:3000...
    start "" "http://localhost:3000"
)

rem Handle Cloudflare Tunnel (simplified - use cloudflare-tunnel-run.bat for tunnel)
set "TUNNEL_URL="
set "TUNNEL_STARTED="

if not defined NO_TUNNEL (
    if not defined RESTART_MODE (
        where cloudflared >nul 2>&1
        if not errorlevel 1 (
            if exist "%USERPROFILE%\.cloudflared\config.yml" (
                echo.
                echo [Info] Cloudflare Tunnel is configured.
                echo        Run cloudflare-tunnel-run.bat to start the tunnel.
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
if "!NETWORK_IPS!"=="" (
    echo   [No Wi-Fi/Ethernet adapter found]
) else (
    call :print_network_ips
)


echo.
echo Press any key to close this launcher...
echo (The backend, frontend, and tunnel will keep running)
pause >nul
goto :eof

:print_network_ips
set "TEMP_IPS=!NETWORK_IPS!"
:print_ips_loop
for /f "tokens=1* delims=|" %%a in ("!TEMP_IPS!") do (
    for /f "tokens=1,2" %%x in ("%%a") do (
        echo   %%x http://%%y:3000
    )
    set "TEMP_IPS=%%b"
)
if not "!TEMP_IPS!"=="" goto :print_ips_loop
goto :eof
