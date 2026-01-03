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
    goto :check_auth
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
:: STEP 3: Check/Setup Authentication
:: ============================================
:check_auth
echo:
echo [3/4] Checking authentication...

:: Test if Claude Code works (will fail if not authenticated)
echo   Testing Claude Code connection...

:: Create a temp file to capture output
set "TEMP_FILE=%TEMP%\claude_test_%RANDOM%.txt"

:: Try a simple query with subscription auth (no API key)
set "ANTHROPIC_API_KEY="
claude -p "Say OK" --max-turns 1 > "%TEMP_FILE%" 2>&1

if %errorlevel% equ 0 (
    echo   [OK] Claude Code is authenticated with Max subscription
    del "%TEMP_FILE%" 2>nul
    goto :install_sdk
)

:: Check if error is about authentication
findstr /i "login\|auth\|token" "%TEMP_FILE%" >nul 2>&1
if %errorlevel% equ 0 (
    del "%TEMP_FILE%" 2>nul
    echo:
    echo   [!] Claude Code is not authenticated.
    echo:
    echo   Opening browser for Max subscription login...
    echo   Please login with your Claude Max account.
    echo:

    claude login

    if !errorlevel! equ 0 (
        echo:
        echo   [OK] Authentication successful!
    ) else (
        echo:
        echo   [X] Authentication failed or cancelled.
        echo   You can try again later by running: claude login
        echo:
        pause
        exit /b 1
    )
) else (
    :: Some other error
    echo   [!] Claude Code test failed:
    type "%TEMP_FILE%"
    del "%TEMP_FILE%" 2>nul
    echo:
    echo   This might be a network issue or Claude Code problem.
    echo   Try running: claude login
    echo:
)

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
echo           Setup Complete!
echo ========================================
echo:
echo Verifying setup...
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

:: Check authentication
echo   Testing authentication...
set "ANTHROPIC_API_KEY="
claude -p "Say OK" --max-turns 1 >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Authenticated with Max subscription
) else (
    echo   [!] Not authenticated - run 'claude login'
)

echo:
echo ----------------------------------------
echo Next steps:
echo   1. Run Lab_Assistant.bat to start the app
echo   2. Select "Claude Opus 4.5" or "Claude Sonnet 4.5" in the model selector
echo   3. Enjoy using Claude with your Max subscription!
echo ----------------------------------------
echo:
pause
