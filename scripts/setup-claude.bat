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
echo [3/4] Checking authentication...

:: Remove API key to force subscription auth
set "ANTHROPIC_API_KEY="

:: Check if already authenticated by looking for token file
set "TOKEN_FILE=%USERPROFILE%\.claude\oauth_token.json"
if exist "%TOKEN_FILE%" (
    echo   [OK] Already authenticated (token file found)
    echo:
    choice /c YN /m "Do you want to re-authenticate? (Y=Yes, N=No)"
    if errorlevel 2 goto :install_sdk
    echo:
    echo   Logging out first...
    claude logout 2>nul
)

echo:
echo   IMPORTANT: When the browser opens, log in with your
echo   Claude Max subscription account (NOT API Console).
echo:
echo   After logging in, the browser will show a success message.
echo   Then return to this window.
echo:
pause

:: Use 'claude auth login' for non-interactive login flow
:: If that doesn't work, fall back to opening browser manually
echo   Opening authentication...

:: Try the auth login command (opens browser, returns when done)
claude auth login 2>nul
if %errorlevel% neq 0 (
    :: Fallback: just tell user to run claude and use /login
    echo:
    echo   [!] Direct login not available in this version.
    echo:
    echo   Please run 'claude' in a terminal and type /login
    echo   Or the login browser should have opened automatically.
    echo:
    pause
)

:: Verify token was created
if exist "%TOKEN_FILE%" (
    echo:
    echo   [OK] Authentication successful!
) else (
    echo:
    echo   [!] Authentication may not have completed.
    echo   If you didn't see a browser, run: claude
    echo   Then type /login inside Claude Code.
    echo:
    choice /c YN /m "Continue anyway? (Y=Yes, N=No)"
    if errorlevel 2 (
        pause
        exit /b 1
    )
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
    echo   [!] No authentication token - run 'claude' then '/login'
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
echo   - Run: claude
echo   - Type: /login
echo   - Log in with your MAX subscription account
echo:
pause
