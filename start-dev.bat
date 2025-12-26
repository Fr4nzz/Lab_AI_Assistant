@echo off
title Lab Assistant Launcher
echo.
echo ========================================
echo    Lab Assistant - Development Mode
echo ========================================
echo.

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
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Opening browser...
start http://localhost:3000

echo.
echo Press any key to close this launcher...
echo (The backend and frontend will keep running)
pause >nul
