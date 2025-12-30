@echo off
setlocal enabledelayedexpansion
title Lab Assistant - Autostart Setup
echo.
echo ========================================
echo    Lab Assistant - Autostart Setup
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "BAT_PATH=%SCRIPT_DIR%Lab_Assistant.bat"
set "ICON_PATH=%SCRIPT_DIR%Lab_Assistant.ico"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "STARTUP_SHORTCUT=%STARTUP_FOLDER%\Lab Assistant.lnk"

:: Check if Lab_Assistant.bat exists
if not exist "%BAT_PATH%" (
    echo [ERROR] Lab_Assistant.bat not found!
    echo Please make sure you're running this from the Lab Assistant folder.
    pause
    exit /b 1
)

:: Check current status
if exist "%STARTUP_SHORTCUT%" (
    echo Current status: ENABLED (Lab Assistant will start on boot)
    echo.
    echo Options:
    echo   1. Disable autostart
    echo   2. Keep enabled
    echo.
    choice /c 12 /n /m "Choose option [1-2]: "
    if errorlevel 2 goto :done
    if errorlevel 1 (
        echo.
        echo Removing autostart...
        del "%STARTUP_SHORTCUT%" 2>nul
        if not exist "%STARTUP_SHORTCUT%" (
            echo [OK] Autostart disabled!
        ) else (
            echo [!] Failed to remove shortcut
        )
        goto :done
    )
) else (
    echo Current status: DISABLED
    echo.
    echo Enabling autostart will:
    echo   - Create a shortcut in Windows Startup folder
    echo   - Lab Assistant will launch when you log in
    echo   - Services run in background (you can close launcher window)
    echo.
    echo Startup folder: %STARTUP_FOLDER%
    echo.
    choice /c YN /n /m "Enable autostart? [Y/N]: "
    if errorlevel 2 goto :done

    echo.
    echo Creating startup shortcut...

    powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $shortcut = $ws.CreateShortcut('%STARTUP_SHORTCUT%'); $shortcut.TargetPath = 'cmd.exe'; $shortcut.Arguments = '/c \"\"%BAT_PATH%\"\"'; $shortcut.WorkingDirectory = '%SCRIPT_DIR%'; $shortcut.Description = 'Start Lab Assistant on boot'; $shortcut.IconLocation = '%ICON_PATH%'; $shortcut.WindowStyle = 7; $shortcut.Save()"

    if exist "%STARTUP_SHORTCUT%" (
        echo [OK] Autostart enabled!
        echo.
        echo Lab Assistant will now start automatically when you log in.
    ) else (
        echo [!] Failed to create startup shortcut
    )
)

:done
echo.
echo ========================================
echo  Manual Configuration
echo ========================================
echo.
echo You can also manage startup apps manually:
echo.
echo   Method 1 - Startup Folder:
echo     1. Press Win+R
echo     2. Type: shell:startup
echo     3. Add or remove shortcuts here
echo.
echo   Method 2 - Task Manager:
echo     1. Press Ctrl+Shift+Esc
echo     2. Go to "Startup apps" tab
echo     3. Enable/disable Lab Assistant
echo.

pause
