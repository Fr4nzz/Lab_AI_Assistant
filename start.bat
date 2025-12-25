@echo off
title Lab Assistant Launcher
echo.
echo ========================================
echo    Lab Assistant Launcher
echo ========================================
echo.

REM Check for flags
set RESTART_DOCKER=0
:parse_args
if "%~1"=="" goto run
if /i "%~1"=="-r" set RESTART_DOCKER=1
if /i "%~1"=="--restart" set RESTART_DOCKER=1
if /i "%~1"=="--restart-docker" set RESTART_DOCKER=1
shift
goto parse_args

:run
if %RESTART_DOCKER%==1 (
    echo Starting Lab Assistant with Docker restart...
) else (
    echo Starting Lab Assistant (quick start - use -r to restart Docker)...
)
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\start-docker.ps1" -RestartDocker:%RESTART_DOCKER%
echo.
echo Press any key to close this window...
pause >nul
