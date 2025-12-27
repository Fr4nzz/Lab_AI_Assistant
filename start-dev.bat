@echo off
setlocal enabledelayedexpansion
title Lab Assistant Launcher
echo.
echo ========================================
echo    Lab Assistant - Development Mode
echo ========================================
echo.

:: Get network IPs (Wi-Fi and Ethernet only, filter out virtual adapters)
set "NETWORK_IPS="
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '127.*' -and $_.InterfaceAlias -match 'Wi-Fi|Wireless|WLAN|^Ethernet' -and $_.InterfaceAlias -notmatch 'VMware|VirtualBox|vEthernet|Hyper-V|WSL' } | ForEach-Object { $_.IPAddress }"') do (
    if "!NETWORK_IPS!"=="" (
        set "NETWORK_IPS=%%i"
    ) else (
        set "NETWORK_IPS=!NETWORK_IPS!,%%i"
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

:: Install frontend dependencies if needed (check for next binary, not just node_modules)
if not exist "%SCRIPT_DIR%frontend\node_modules\.bin\next.cmd" (
    echo Installing frontend dependencies...
    cd /d "%SCRIPT_DIR%frontend"
    :: Remove old node_modules if it exists but is broken
    if exist node_modules rmdir /s /q node_modules
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

echo.
echo ========================================
echo    Lab Assistant Started!
echo ========================================
echo.
echo Local access:
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo.
echo Network access (other devices):
if not "!NETWORK_IPS!"=="" (
    for %%a in (!NETWORK_IPS!) do (
        echo   http://%%a:3000
    )
) else (
    echo   [No Wi-Fi/Ethernet adapter found]
)
echo.
echo Opening browser...
start http://localhost:3000

echo.
echo Press any key to close this launcher...
echo (The backend and frontend will keep running)
pause >nul
