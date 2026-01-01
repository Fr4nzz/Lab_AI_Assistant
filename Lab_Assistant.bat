@echo off
setlocal enabledelayedexpansion
title Lab Assistant
echo:
echo ========================================
echo        Lab Assistant Launcher
echo ========================================
echo:

:: Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

:: Parse command line arguments
set "DEBUG_MODE="
set "NO_TUNNEL="
set "NO_TELEGRAM="
set "RESTART_MODE="
set "INSTALL_DEPS="
set "STOP_MODE="
set "STATUS_MODE="

:parse_args
if "%~1"=="" goto :done_args
if /i "%~1"=="--debug" set "DEBUG_MODE=1"
if /i "%~1"=="--no-tunnel" set "NO_TUNNEL=1"
if /i "%~1"=="--no-telegram" set "NO_TELEGRAM=1"
if /i "%~1"=="--restart" set "RESTART_MODE=1"
if /i "%~1"=="--install" set "INSTALL_DEPS=1"
if /i "%~1"=="--stop" set "STOP_MODE=1"
if /i "%~1"=="--status" set "STATUS_MODE=1"
shift
goto :parse_args
:done_args

:: Handle --stop flag: stop all services and exit
if defined STOP_MODE (
    echo Stopping all Lab Assistant services...
    echo:
    call :stop_all_services
    echo:
    echo All services stopped.
    pause
    exit /b 0
)

:: Handle --status flag: check if services are running and exit
if defined STATUS_MODE (
    call :check_status
    pause
    exit /b 0
)

:: Set window style based on debug mode
:: DEBUG: visible windows that stay open on exit (cmd /k)
:: NORMAL: completely hidden background processes (PowerShell -WindowStyle Hidden)
if defined DEBUG_MODE (
    set "RUN_HIDDEN="
) else (
    set "RUN_HIDDEN=1"
)

:: Create logs directory for silent mode
if defined RUN_HIDDEN (
    if not exist "%SCRIPT_DIR%logs" mkdir "%SCRIPT_DIR%logs"
)

:: ============================================
:: STEP 1: Check Prerequisites
:: ============================================
echo [1/4] Checking prerequisites...
echo:

:: Check if Python is available
set "PYTHON_OK="
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_OK=1"
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo   [OK] Python %%v found
) else (
    echo   [X] Python not found
)

:: Check if Node.js/npm is available
set "NODE_OK="
set "NODE_PATH="

:: First try the PATH
where node >nul 2>&1
if %errorlevel% equ 0 (
    set "NODE_OK=1"
    set "NODE_PATH=node"
)

:: Check common installation paths if not in PATH
if not defined NODE_OK (
    if exist "C:\Program Files\nodejs\node.exe" (
        set "NODE_OK=1"
        set "NODE_PATH=C:\Program Files\nodejs\node.exe"
        set "PATH=C:\Program Files\nodejs;!PATH!"
    )
)
if not defined NODE_OK (
    if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\node.exe" (
        set "NODE_OK=1"
        set "NODE_PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links\node.exe"
        set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;!PATH!"
    )
)
if not defined NODE_OK (
    if exist "%PROGRAMFILES%\nodejs\node.exe" (
        set "NODE_OK=1"
        set "NODE_PATH=%PROGRAMFILES%\nodejs\node.exe"
        set "PATH=%PROGRAMFILES%\nodejs;!PATH!"
    )
)

if defined NODE_OK (
    for /f "tokens=1" %%v in ('"!NODE_PATH!" --version 2^>^&1') do echo   [OK] Node.js %%v found
) else (
    echo   [X] Node.js not found
)

:: Check if npm is available (separate check)
set "NPM_OK="
where npm >nul 2>&1
if %errorlevel% equ 0 (
    set "NPM_OK=1"
) else (
    if exist "C:\Program Files\nodejs\npm.cmd" set "NPM_OK=1"
    if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\npm.cmd" set "NPM_OK=1"
)
if not defined NPM_OK (
    if defined NODE_OK (
        echo   [X] npm not found - Node.js installed but npm missing from PATH
    )
)

echo:

:: If missing prerequisites, offer to install
if not defined PYTHON_OK (
    echo ========================================
    echo  Python is required but not installed
    echo ========================================
    echo:
    echo Options:
    echo   1. Install via winget - recommended
    echo   2. Open Python download page
    echo   3. Skip - I will install manually
    echo:
    choice /c 123 /n /m "Choose option [1-3]: "
    if errorlevel 3 goto :skip_python
    if errorlevel 2 (
        echo Opening Python download page...
        start "" "https://www.python.org/downloads/"
        echo:
        echo Please install Python, then restart this script.
        pause
        exit /b 1
    )
    if errorlevel 1 (
        echo:
        echo Installing Python via winget...
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        if !errorlevel! equ 0 (
            echo:
            echo [OK] Python installed successfully!
            echo:
            echo IMPORTANT: Please close this window and open a NEW terminal,
            echo then run Lab_Assistant.bat again.
            echo:
            pause
            exit /b 0
        ) else (
            echo:
            echo [!] winget installation failed. Please install Python manually:
            start "" "https://www.python.org/downloads/"
            pause
            exit /b 1
        )
    )
)
:skip_python

if not defined NODE_OK (
    echo ========================================
    echo  Node.js is required but not installed
    echo ========================================
    echo:
    echo Options:
    echo   1. Install via winget - recommended
    echo   2. Open Node.js download page
    echo   3. Skip - I will install manually
    echo:
    choice /c 123 /n /m "Choose option [1-3]: "
    if errorlevel 3 goto :skip_node
    if errorlevel 2 (
        echo Opening Node.js download page...
        start "" "https://nodejs.org/"
        echo:
        echo Please install Node.js LTS, then restart this script.
        pause
        exit /b 1
    )
    if errorlevel 1 (
        echo:
        echo Installing Node.js via winget...
        winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
        if !errorlevel! equ 0 (
            echo:
            echo [OK] Node.js installed successfully!
            echo:
            echo IMPORTANT: Please close this window and open a NEW terminal,
            echo then run Lab_Assistant.bat again.
            echo:
            pause
            exit /b 0
        ) else (
            echo:
            echo [!] winget installation failed. Please install Node.js manually:
            start "" "https://nodejs.org/"
            pause
            exit /b 1
        )
    )
)
:skip_node

:: Final check - exit if still missing
if not defined PYTHON_OK (
    echo [ERROR] Python is required. Please install it and try again.
    pause
    exit /b 1
)
if not defined NODE_OK (
    echo [ERROR] Node.js is required. Please install it and try again.
    pause
    exit /b 1
)
if not defined NPM_OK (
    echo [ERROR] npm not found. Please reinstall Node.js and try again.
    pause
    exit /b 1
)

:: ============================================
:: STEP 2: Stop Existing Processes
:: ============================================
echo [2/4] Stopping existing processes...

:: Kill processes on our ports
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" 2>nul
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" 2>nul
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 24678 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" 2>nul

timeout /t 1 /nobreak >nul

:: Close all Lab Assistant windows
taskkill /FI "WINDOWTITLE eq Lab Assistant - Backend*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Lab Assistant - Frontend*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Lab Assistant - Telegram*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Lab Assistant - Tunnel*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Cloudflare Quick Tunnel*" /F 2>nul
powershell -NoProfile -Command "Get-Process | Where-Object { $_.ProcessName -eq 'cmd' -and $_.MainWindowTitle -like '*Lab Assistant*' -and $_.MainWindowTitle -ne 'Lab Assistant' } | Stop-Process -Force -ErrorAction SilentlyContinue" 2>nul
taskkill /IM cloudflared.exe /F 2>nul

timeout /t 1 /nobreak >nul

:: ============================================
:: STEP 3: Load Environment & Install Deps
:: ============================================
echo [3/4] Loading configuration...

:: Load environment variables from root .env file
if exist "%SCRIPT_DIR%.env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%SCRIPT_DIR%.env") do (
        if not "%%a"=="" set "%%a=%%b"
    )
    echo   [OK] Loaded .env configuration
) else (
    echo   [!] No .env file found - using defaults
)

:: Install backend dependencies
echo:
echo   Installing backend dependencies
cd /d "%SCRIPT_DIR%backend"
python -m pip install -r requirements.txt -q >nul 2>&1
cd /d "%SCRIPT_DIR%"

:: Install frontend dependencies if needed
set "NEED_INSTALL="
if not exist "%SCRIPT_DIR%frontend-nuxt\node_modules\.bin\nuxt.cmd" set "NEED_INSTALL=1"
if not exist "%SCRIPT_DIR%frontend-nuxt\node_modules\nuxt" set "NEED_INSTALL=1"
if not exist "%SCRIPT_DIR%frontend-nuxt\node_modules\better-sqlite3" set "NEED_INSTALL=1"
if defined INSTALL_DEPS set "NEED_INSTALL=1"

if defined NEED_INSTALL (
    echo   Installing frontend dependencies - this may take a few minutes
    cd /d "%SCRIPT_DIR%frontend-nuxt"
    call npm install
    cd /d "%SCRIPT_DIR%"
) else (
    echo   [OK] Frontend dependencies already installed
)

:: Install telegram bot dependencies if token is configured
if defined TELEGRAM_BOT_TOKEN (
    if not defined NO_TELEGRAM (
        python -m pip show python-telegram-bot >nul 2>&1
        if !errorlevel! neq 0 (
            echo   Installing Telegram bot dependencies
            python -m pip install -r "%SCRIPT_DIR%telegram_bot\requirements.txt" -q >nul 2>&1
        )
        python -m pip show httpx-sse >nul 2>&1
        if !errorlevel! neq 0 (
            python -m pip install httpx-sse -q >nul 2>&1
        )
    )
)

:: ============================================
:: STEP 4: Start Services
:: ============================================
echo [4/4] Starting services...
echo:

:: Get network IPs for display
set "NETWORK_IPS="
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "$ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '127.*' -and $_.InterfaceAlias -match 'Wi-Fi|Wireless|WLAN|Ethernet' -and $_.InterfaceAlias -notmatch 'VMware|VirtualBox|vEthernet|Hyper-V|WSL' }; foreach($ip in $ips) { if($ip.InterfaceAlias -match 'Wi-Fi|Wireless|WLAN') { Write-Host '[Wi-Fi]' $ip.IPAddress } else { Write-Host '[Ethernet]' $ip.IPAddress } }"`) do (
    if "!NETWORK_IPS!"=="" (
        set "NETWORK_IPS=%%i"
    ) else (
        set "NETWORK_IPS=!NETWORK_IPS!|%%i"
    )
)

:: Start Backend
echo   Starting Backend...
if defined RUN_HIDDEN (
    powershell -NoProfile -Command "Start-Process -FilePath 'cmd' -ArgumentList '/c cd /d \"%SCRIPT_DIR%backend\" && python server.py > \"%SCRIPT_DIR%logs\backend.log\" 2>&1' -WindowStyle Hidden"
) else (
    start "Lab Assistant - Backend" cmd /k "cd /d %SCRIPT_DIR%backend && python server.py"
)
timeout /t 3 /nobreak >nul

:: Start Frontend
echo   Starting Frontend...
if defined RUN_HIDDEN (
    powershell -NoProfile -Command "Start-Process -FilePath 'cmd' -ArgumentList '/c cd /d \"%SCRIPT_DIR%frontend-nuxt\" && npm run dev > \"%SCRIPT_DIR%logs\frontend.log\" 2>&1' -WindowStyle Hidden"
) else (
    start "Lab Assistant - Frontend" cmd /k "cd /d %SCRIPT_DIR%frontend-nuxt && npm run dev"
)
timeout /t 5 /nobreak >nul

:: Start Telegram bot if configured
set "TELEGRAM_STARTED="
if defined TELEGRAM_BOT_TOKEN (
    if not defined NO_TELEGRAM (
        echo   Starting Telegram Bot...
        call :start_telegram_bot
        set "TELEGRAM_STARTED=1"
    ) else (
        echo   [!] Telegram Bot disabled via --no-telegram
    )
) else (
    echo   [!] Telegram Bot skipped - TELEGRAM_BOT_TOKEN not set in .env
)

:: Start Cloudflare Tunnel (auto-start unless --no-tunnel)
set "TUNNEL_STARTED="
if not defined NO_TUNNEL (
    call :start_cloudflare_tunnel
)

:: Open browser (skip in restart mode)
if not defined RESTART_MODE (
    timeout /t 2 /nobreak >nul
    start "" "http://localhost:3000"
)

:: ============================================
:: Display Status
:: ============================================
echo:
echo ========================================
echo      Lab Assistant is Running!
echo ========================================
echo:
echo  Local Access:
echo    Frontend: http://localhost:3000
echo    Backend:  http://localhost:8000
echo:
echo  Network Access (LAN):
if "!NETWORK_IPS!"=="" (
    echo    No network adapters found
) else (
    call :print_network_ips
)
echo:
echo  Services:
echo    [*] Backend
echo    [*] Frontend
if defined TELEGRAM_STARTED (
    echo    [*] Telegram Bot
) else (
    echo    [ ] Telegram Bot - not configured
)
if defined TUNNEL_STARTED (
    echo    [*] Cloudflare Tunnel
) else (
    echo    [ ] Cloudflare Tunnel - disabled
)
echo:
if defined DEBUG_MODE (
    echo  Mode: DEBUG - windows visible
) else (
    echo  Mode: Silent - services running in background
    echo  Logs: logs\backend.log, frontend.log, telegram.log, tunnel.log
)
echo:
echo  Commands:
echo    --debug    Show console windows
echo    --stop     Stop all services
echo    --status   Check if services are running
echo ----------------------------------------
echo  Press any key to close this window
echo  Services will keep running in background
echo ----------------------------------------
pause >nul
goto :eof

:: ============================================
:: Helper Functions
:: ============================================

:print_network_ips
set "TEMP_IPS=!NETWORK_IPS!"
:print_ips_loop
for /f "tokens=1* delims=|" %%a in ("!TEMP_IPS!") do (
    for /f "tokens=1,2" %%x in ("%%a") do (
        echo    %%x http://%%y:3000
    )
    set "TEMP_IPS=%%b"
)
if not "!TEMP_IPS!"=="" goto :print_ips_loop
goto :eof

:start_telegram_bot
if defined RUN_HIDDEN (
    powershell -NoProfile -Command "Start-Process -FilePath 'cmd' -ArgumentList '/c cd /d \"%SCRIPT_DIR%\" && python -m telegram_bot.bot > \"%SCRIPT_DIR%logs\telegram.log\" 2>&1' -WindowStyle Hidden"
) else (
    start "Lab Assistant - Telegram Bot" cmd /k "cd /d %SCRIPT_DIR% && python -m telegram_bot.bot"
)
goto :eof

:start_cloudflare_tunnel
:: Start Cloudflare tunnel
set "DATA_DIR=%SCRIPT_DIR%data"
set "URL_FILE=%DATA_DIR%\tunnel_url.txt"
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"

:: Find cloudflared
set "CLOUDFLARED_CMD="
where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
    set "CLOUDFLARED_CMD=cloudflared"
) else if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe" (
    set "CLOUDFLARED_CMD=%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe"
)

if not defined CLOUDFLARED_CMD (
    echo   [!] cloudflared not found - run cloudflare-quick-tunnel.bat manually first
    goto :eof
)

echo   Starting Cloudflare Tunnel...
if defined RUN_HIDDEN (
    :: Use helper script for cleaner startup
    powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\start-tunnel.ps1" -CloudflaredPath "%CLOUDFLARED_CMD%" -LogFile "%SCRIPT_DIR%logs\tunnel.log" -UrlFile "%URL_FILE%"
) else (
    start "Lab Assistant - Tunnel" cmd /k "cd /d %SCRIPT_DIR% && cloudflare-quick-tunnel.bat"
)
set "TUNNEL_STARTED=1"
goto :eof

:stop_all_services
echo   Stopping processes on ports 8000, 3000, 24678...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" 2>nul
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" 2>nul
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 24678 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" 2>nul
timeout /t 1 /nobreak >nul

echo   Stopping Lab Assistant windows...
taskkill /FI "WINDOWTITLE eq Lab Assistant - Backend*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Lab Assistant - Frontend*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Lab Assistant - Telegram*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Lab Assistant - Tunnel*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Cloudflare Quick Tunnel*" /F 2>nul
powershell -NoProfile -Command "Get-Process | Where-Object { $_.ProcessName -eq 'cmd' -and $_.MainWindowTitle -like '*Lab Assistant*' -and $_.MainWindowTitle -ne 'Lab Assistant' } | Stop-Process -Force -ErrorAction SilentlyContinue" 2>nul

echo   Stopping Cloudflare tunnel...
taskkill /IM cloudflared.exe /F 2>nul

echo   Stopping Telegram bot...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*telegram_bot*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul

timeout /t 1 /nobreak >nul
goto :eof

:check_status
echo:
echo ========================================
echo     Lab Assistant Service Status
echo ========================================
echo:
set "SCRIPT_DIR=%~dp0"

:: Check Backend (port 8000)
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; if($c) { exit 0 } else { exit 1 }" 2>nul
if %errorlevel% equ 0 (
    echo  [RUNNING] Backend        - port 8000
) else (
    echo  [STOPPED] Backend        - port 8000
)

:: Check Frontend (port 3000)
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue; if($c) { exit 0 } else { exit 1 }" 2>nul
if %errorlevel% equ 0 (
    echo  [RUNNING] Frontend       - port 3000
) else (
    echo  [STOPPED] Frontend       - port 3000
)

:: Check Telegram bot (python process with telegram_bot in command line)
:: Use Get-CimInstance to access CommandLine property
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*telegram_bot*' }; if($p) { exit 0 } else { exit 1 }" 2>nul
if %errorlevel% equ 0 (
    echo  [RUNNING] Telegram Bot
) else (
    echo  [STOPPED] Telegram Bot
)

:: Check Cloudflare tunnel (cloudflared.exe process)
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process -Filter \"Name='cloudflared.exe'\" -ErrorAction SilentlyContinue; if($p) { exit 0 } else { exit 1 }" 2>nul
if %errorlevel% equ 0 (
    echo  [RUNNING] Cloudflare Tunnel
) else (
    echo  [STOPPED] Cloudflare Tunnel
)

echo:
echo ----------------------------------------
echo  Log files location: %SCRIPT_DIR%logs\
echo    backend.log, frontend.log
echo    telegram.log, tunnel.log
echo ----------------------------------------
goto :eof
