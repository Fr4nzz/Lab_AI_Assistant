@echo off
setlocal enabledelayedexpansion
:: Wrapper script to run services with proper environment variable inheritance
:: Usage: run-service.bat <service_type> <script_dir>
::   service_type: backend, telegram, frontend
::   script_dir: path to Lab_AI_Assistant root

set "SERVICE_TYPE=%~1"
set "SCRIPT_DIR=%~2"

:: Ensure script_dir ends with backslash
if not "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR!\"

:: Load .env file (handles special characters properly)
if exist "!SCRIPT_DIR!.env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in ("!SCRIPT_DIR!.env") do (
        if not "%%a"=="" set "%%a=%%b"
    )
)

:: Create logs directory
if not exist "!SCRIPT_DIR!logs" mkdir "!SCRIPT_DIR!logs"

:: Run the appropriate service (use > to overwrite log on each restart)
if /i "!SERVICE_TYPE!"=="backend" (
    cd /d "!SCRIPT_DIR!backend"
    python server.py > "!SCRIPT_DIR!logs\backend.log" 2>&1
) else if /i "!SERVICE_TYPE!"=="telegram" (
    cd /d "!SCRIPT_DIR!"
    python -m telegram_bot.bot > "!SCRIPT_DIR!logs\telegram.log" 2>&1
) else if /i "!SERVICE_TYPE!"=="frontend" (
    cd /d "!SCRIPT_DIR!frontend-nuxt"
    call npm run dev > "!SCRIPT_DIR!logs\frontend.log" 2>&1
) else (
    echo Unknown service type: !SERVICE_TYPE!
    exit /b 1
)
