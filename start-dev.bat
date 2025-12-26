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

:: Check if pnpm is available
where pnpm >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: pnpm not found in PATH
    echo Install with: npm install -g pnpm
    pause
    exit /b 1
)

:: Install backend dependencies if needed
if not exist "%SCRIPT_DIR%backend\venv" (
    echo Installing backend dependencies...
    cd /d "%SCRIPT_DIR%backend"
    python -m pip install -r requirements.txt
    cd /d "%SCRIPT_DIR%"
)

:: Install frontend dependencies if needed
if not exist "%SCRIPT_DIR%frontend\node_modules" (
    echo Installing frontend dependencies...
    cd /d "%SCRIPT_DIR%frontend"
    pnpm install
    cd /d "%SCRIPT_DIR%"
)

echo.
echo Starting Backend (Python FastAPI on port 8000)...
start "Lab Assistant - Backend" cmd /k "cd /d %SCRIPT_DIR%backend && python server.py"

:: Wait a moment for backend to start
timeout /t 3 /nobreak >nul

echo Starting Frontend (Next.js on port 3000)...
start "Lab Assistant - Frontend" cmd /k "cd /d %SCRIPT_DIR%frontend && pnpm dev"

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
