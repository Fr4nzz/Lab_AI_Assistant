@echo off
title Lab Assistant - Telegram Bot
echo.
echo ========================================
echo    Lab Assistant - Telegram Bot
echo ========================================
echo.

:: Get script directory
set "SCRIPT_DIR=%~dp0"

:: Load environment variables from .env
if exist "%SCRIPT_DIR%.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%SCRIPT_DIR%.env") do (
        set "LINE=%%a"
        if not "!LINE:~0,1!"=="#" if not "!LINE!"=="" (
            set "%%a=%%b"
        )
    )
)

:: Check for bot token
if not defined TELEGRAM_BOT_TOKEN (
    echo ERROR: TELEGRAM_BOT_TOKEN not set in .env file!
    echo.
    echo To set up the Telegram bot:
    echo   1. Message @BotFather on Telegram
    echo   2. Send /newbot and follow instructions
    echo   3. Copy the token and add to .env:
    echo      TELEGRAM_BOT_TOKEN=your_token_here
    echo.
    echo See docs/TELEGRAM_BOT_SETUP.md for detailed instructions.
    echo.
    pause
    exit /b 1
)

:: Check for Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH
    echo Please install Python and add it to PATH
    pause
    exit /b 1
)

:: Install dependencies if needed
echo Checking dependencies...
pip show python-telegram-bot >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing telegram bot dependencies...
    pip install -r "%SCRIPT_DIR%telegram_bot\requirements.txt"
)
pip show httpx-sse >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing httpx-sse...
    pip install httpx-sse
)

echo.
echo Starting Telegram bot...
echo.
echo Make sure the backend is running (start-dev.bat)
echo.

:: Run the bot
cd /d "%SCRIPT_DIR%"
python -m telegram_bot.bot

pause
