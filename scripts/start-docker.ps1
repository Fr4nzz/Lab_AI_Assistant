# Start Lab Assistant with Docker for LobeChat (Windows PowerShell)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Starting Lab Assistant" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check if Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "Error: Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Start backend in new window
Write-Host "Starting backend on http://localhost:8000" -ForegroundColor Green
$BackendDir = Join-Path $ProjectDir "backend"

# Kill any existing process on port 8000
Write-Host "Checking for existing backend..." -ForegroundColor Yellow
$existingPid = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess | Select-Object -First 1
if ($existingPid) {
    Write-Host "Stopping existing backend (PID: $existingPid)..." -ForegroundColor Yellow
    Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Close any Edge instances using our profile (prevents lock issues)
Write-Host "Closing any existing Edge instances..." -ForegroundColor Yellow
Get-Process msedge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendDir'; python server.py"

# Wait for backend
Write-Host "Waiting for backend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Start LobeChat via Docker
Write-Host "Starting LobeChat frontend on http://localhost:3210" -ForegroundColor Green

# Stop existing container if running (ignore errors if not exists)
$ErrorActionPreference = "SilentlyContinue"
docker stop lobe-chat 2>&1 | Out-Null
docker rm lobe-chat 2>&1 | Out-Null
$ErrorActionPreference = "Stop"

# Run LobeChat with our backend as the OpenAI proxy
docker run -d `
    --name lobe-chat `
    -p 3210:3210 `
    -e OPENAI_PROXY_URL=http://host.docker.internal:8000/v1 `
    -e OPENAI_API_KEY=dummy-key `
    -e "OPENAI_MODEL_LIST=+lab-assistant=Lab Assistant<100000:vision:fc>" `
    --add-host=host.docker.internal:host-gateway `
    lobehub/lobe-chat

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Lab Assistant is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:3210" -ForegroundColor Yellow
Write-Host ""
Write-Host "To stop:" -ForegroundColor Cyan
Write-Host "  - Close the backend PowerShell window" -ForegroundColor White
Write-Host "  - Run: docker stop lobe-chat" -ForegroundColor White
