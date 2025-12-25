@echo off
title Lab Assistant Launcher
echo.
echo ========================================
echo    Lab Assistant Launcher
echo ========================================
echo.
echo Starting Lab Assistant (Backend local + Frontend Docker)...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\start-docker.ps1"
echo.
echo Press any key to close this window...
pause >nul
