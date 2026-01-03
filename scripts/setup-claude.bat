@echo off
setlocal enabledelayedexpansion
title Claude Code Setup for Lab Assistant

echo:
echo ========================================
echo    Claude Code Setup for Lab Assistant
echo ========================================
echo:
echo This script will:
echo   1. Check/install Claude Code CLI
echo   2. Authenticate with your Max subscription
echo   3. Install Python SDK
echo   4. Verify everything works
echo:
pause

:: Get the script directory
set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
cd /d "%ROOT_DIR%"

:: ============================================
:: STEP 1: Check Node.js
:: ============================================
echo:
echo [1/4] Checking Node.js...

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo   [X] Node.js not found!
    echo:
    echo   Node.js is required to install Claude Code.
    echo   Please install Node.js first: https://nodejs.org/
    echo:
    pause
    exit /b 1
)

for /f "tokens=1" %%v in ('node --version 2^>^&1') do echo   [OK] Node.js %%v found

:: ============================================
:: STEP 2: Check/Install Claude Code CLI
:: ============================================
echo:
echo [2/4] Checking Claude Code CLI...

where claude >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('claude --version 2^>^&1') do echo   [OK] Claude Code %%v already installed
    goto :authenticate
)

echo   Claude Code CLI not found. Installing...
echo:
call npm install -g @anthropic-ai/claude-code

if %errorlevel% neq 0 (
    echo:
    echo   [X] Failed to install Claude Code CLI
    echo   Try running this command manually in PowerShell as Administrator:
    echo     npm install -g @anthropic-ai/claude-code
    echo:
    pause
    exit /b 1
)

:: Verify installation
where claude >nul 2>&1
if %errorlevel% neq 0 (
    echo:
    echo   [!] Claude Code installed but not in PATH.
    echo   Please close this window, open a NEW terminal, and run this script again.
    echo:
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('claude --version 2^>^&1') do echo   [OK] Claude Code %%v installed

:: ============================================
:: STEP 3: Authenticate with Max subscription
:: ============================================
:authenticate
echo:
echo [3/4] Authenticating with Max subscription...
echo:
echo   IMPORTANT: When the browser opens, log in with your
echo   Claude Max subscription account (NOT API Console).
echo:
echo   If you have an ANTHROPIC_API_KEY set, it will be ignored
echo   so that your Max subscription is used instead.
echo:

:: Remove API key to force subscription auth
set "ANTHROPIC_API_KEY="

:: Check if already authenticated by looking for token file
set "TOKEN_FILE=%USERPROFILE%\.claude\oauth_token.json"
if exist "%TOKEN_FILE%" (
    echo   Found existing authentication token.
    echo:
    choice /c YN /m "Do you want to re-authenticate? (Y=Yes, N=No)"
    if errorlevel 2 goto :install_sdk
)

echo:
echo   Opening browser for authentication...
echo   Please complete the login in your browser.
echo:

:: Run claude login
claude login

if %errorlevel% neq 0 (
    echo:
    echo   [!] Authentication may have failed or was cancelled.
    echo   You can try again later by running: claude login
    echo:
    choice /c YN /m "Continue anyway? (Y=Yes, N=No)"
    if errorlevel 2 (
        pause
        exit /b 1
    )
)

echo:
echo   [OK] Authentication completed!

:: ============================================
:: STEP 4: Install Python SDK
:: ============================================
:install_sdk
echo:
echo [4/4] Installing Python SDK...

python -m pip show claude-agent-sdk >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] claude-agent-sdk already installed
) else (
    echo   Installing claude-agent-sdk...
    python -m pip install claude-agent-sdk -q
    if !errorlevel! equ 0 (
        echo   [OK] claude-agent-sdk installed
    ) else (
        echo   [!] Failed to install claude-agent-sdk
        echo   Try manually: pip install claude-agent-sdk
    )
)

:: ============================================
:: VERIFICATION
:: ============================================
echo:
echo ========================================
echo           Verifying Setup
echo ========================================
echo:

:: Check CLI
where claude >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Claude Code CLI installed
) else (
    echo   [X] Claude Code CLI not found
)

:: Check Python SDK
python -m pip show claude-agent-sdk >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Python SDK installed
) else (
    echo   [X] Python SDK not installed
)

:: Check token file exists
if exist "%USERPROFILE%\.claude\oauth_token.json" (
    echo   [OK] Authentication token found
) else (
    echo   [!] No authentication token - run 'claude login'
)

:: Quick test (with timeout to prevent hanging)
echo:
echo   Testing Claude Code (this may take a few seconds)...
set "ANTHROPIC_API_KEY="

:: Use timeout command to prevent hanging (Windows)
:: Run test in background and wait max 30 seconds
set "TEST_PASSED=0"
for /f "delims=" %%i in ('claude -p "Say OK" --max-turns 1 2^>^&1') do (
    echo %%i | findstr /i "OK" >nul && set "TEST_PASSED=1"
)

if "%TEST_PASSED%"=="1" (
    echo   [OK] Claude Code is working with Max subscription!
) else (
    echo   [!] Test inconclusive - Claude may still work
    echo       If you see errors, try: claude login
)

echo:
echo ========================================
echo           Setup Complete!
echo ========================================
echo:
echo Next steps:
echo   1. Run Lab_Assistant.bat to start the app
echo   2. Select "Claude Opus 4.5" in the model selector
echo   3. Enjoy using Claude with your Max subscription!
echo:
echo If Claude doesn't work:
echo   - Run: claude login
echo   - Make sure you log in with your MAX subscription account
echo   - Don't use API Console credentials
echo:
pause
