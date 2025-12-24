# Start both backend and frontend for Lab Assistant (Windows PowerShell)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

# Check if frontend exists, if not set it up
$FrontendDir = Join-Path $ProjectDir "frontend-lobechat"
if (-not (Test-Path $FrontendDir)) {
    Write-Host "Frontend not found. Running setup..." -ForegroundColor Yellow
    & (Join-Path $ScriptDir "setup-frontend.ps1")
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Starting Lab Assistant" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Start backend in new window
Write-Host "Starting backend on http://localhost:8000" -ForegroundColor Green
$BackendDir = Join-Path $ProjectDir "backend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendDir'; python server.py"

# Wait for backend
Write-Host "Waiting for backend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Start frontend in new window
Write-Host "Starting frontend on http://localhost:3210" -ForegroundColor Green
if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FrontendDir'; pnpm dev"
} else {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FrontendDir'; npm run dev"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Lab Assistant is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:3210" -ForegroundColor Yellow
Write-Host ""
Write-Host "Close the PowerShell windows to stop the services" -ForegroundColor Cyan
