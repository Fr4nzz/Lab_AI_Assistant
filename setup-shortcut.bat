@echo off
setlocal enabledelayedexpansion
title Lab Assistant - Shortcut Setup
echo.
echo ========================================
echo    Lab Assistant - Shortcut Setup
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "BAT_PATH=%SCRIPT_DIR%Lab_Assistant.bat"
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT_PATH=%DESKTOP%\Lab Assistant.lnk"

:: Check if Lab_Assistant.bat exists
if not exist "%BAT_PATH%" (
    echo [ERROR] Lab_Assistant.bat not found!
    echo Please make sure you're running this from the Lab Assistant folder.
    pause
    exit /b 1
)

echo This script will create:
echo.
echo   1. Desktop shortcut: %SHORTCUT_PATH%
echo.

choice /c YN /n /m "Create desktop shortcut? [Y/N]: "
if errorlevel 2 goto :skip_desktop

:: Create desktop shortcut using PowerShell
echo.
echo Creating desktop shortcut...

powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
    $shortcut = $ws.CreateShortcut('%SHORTCUT_PATH%'); ^
    $shortcut.TargetPath = 'cmd.exe'; ^
    $shortcut.Arguments = '/c \"\"%BAT_PATH%\"\"'; ^
    $shortcut.WorkingDirectory = '%SCRIPT_DIR%'; ^
    $shortcut.Description = 'Start Lab Assistant'; ^
    $shortcut.IconLocation = 'shell32.dll,21'; ^
    $shortcut.Save()"

if %errorlevel% equ 0 (
    echo [OK] Desktop shortcut created!
) else (
    echo [!] Failed to create shortcut
)

:skip_desktop

echo.
echo ========================================
echo  Shortcut Icons
echo ========================================
echo.
echo The shortcut uses a default Windows icon.
echo.
echo To use a custom icon:
echo   1. Right-click the shortcut on your desktop
echo   2. Select "Properties"
echo   3. Click "Change Icon..."
echo   4. Browse to your custom .ico file
echo.
echo You can find free icons at:
echo   - https://icon-icons.com/
echo   - https://www.flaticon.com/
echo   - Search "laboratory icon .ico"
echo.

pause
