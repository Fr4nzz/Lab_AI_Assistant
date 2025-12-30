@echo off
title Quick Tunnel with WhatsApp Notification
echo.
echo ========================================
echo    Quick Tunnel + WhatsApp Notification
echo ========================================
echo.

:: Load WHATSAPP_NOTIFY_PHONE from .env file if it exists
set "ENV_FILE=%~dp0frontend-nuxt\.env"
if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%ENV_FILE%") do (
        if "%%a"=="WHATSAPP_NOTIFY_PHONE" set "WHATSAPP_NOTIFY_PHONE=%%b"
    )
)

:: Use provided argument, env variable, or show error
if not "%~1"=="" (
    echo Using phone from argument: %~1
    set "PHONE=%~1"
) else if defined WHATSAPP_NOTIFY_PHONE (
    echo Using phone from .env: %WHATSAPP_NOTIFY_PHONE%
    set "PHONE=%WHATSAPP_NOTIFY_PHONE%"
) else (
    echo No phone number configured.
    echo.
    echo Options:
    echo   1. Set WHATSAPP_NOTIFY_PHONE in frontend-nuxt\.env
    echo   2. Run: cloudflare-quick-tunnel-notify.bat +1234567890
    echo.
)

echo.

:: Run Python script (it will use WHATSAPP_NOTIFY_PHONE env var or argument)
if defined PHONE (
    python "%~dp0cloudflare-quick-tunnel-notify.py" %PHONE%
) else (
    python "%~dp0cloudflare-quick-tunnel-notify.py" --no-notify
)
