# Start Lab Assistant - Backend local + Frontend Docker (Windows PowerShell)
# This is the RECOMMENDED way to run Lab Assistant for development

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

# Get local IP address for network access
function Get-LocalIP {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 |
           Where-Object { $_.PrefixOrigin -eq 'Dhcp' -or $_.PrefixOrigin -eq 'Manual' } |
           Where-Object { $_.InterfaceAlias -notmatch 'vEthernet|Loopback|WSL' } |
           Select-Object -First 1).IPAddress
    if (-not $ip) {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 |
               Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '127.*' } |
               Select-Object -First 1).IPAddress
    }
    return $ip
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Starting Lab Assistant" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check if Docker is running
try {
    docker info 2>&1 | Out-Null
} catch {
    Write-Host "Error: Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Stop any existing frontend container (ignore errors if not exists)
Write-Host "Cleaning up existing containers..." -ForegroundColor Yellow
$ErrorActionPreference = "SilentlyContinue"
docker stop lobe-chat 2>&1 | Out-Null
docker rm lobe-chat 2>&1 | Out-Null

# Also stop docker-compose frontend if running
Set-Location $ProjectDir
docker-compose stop frontend 2>&1 | Out-Null
docker-compose rm -f frontend 2>&1 | Out-Null
$ErrorActionPreference = "Stop"

# Kill any existing process on port 8000
Write-Host "Checking for existing backend..." -ForegroundColor Yellow
$existingPid = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess | Select-Object -First 1
if ($existingPid) {
    Write-Host "Stopping existing backend (PID: $existingPid)..." -ForegroundColor Yellow
    Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Check if port 3210 is in use
$port3210 = Get-NetTCPConnection -LocalPort 3210 -ErrorAction SilentlyContinue
if ($port3210) {
    Write-Host "Port 3210 is in use. Cleaning up..." -ForegroundColor Yellow
    $port3210.OwningProcess | ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

# Close any Edge instances using our profile (prevents lock issues)
Write-Host "Closing any existing Edge instances..." -ForegroundColor Yellow
Get-Process msedge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Start backend in new window
Write-Host "Starting backend..." -ForegroundColor Green
$BackendDir = Join-Path $ProjectDir "backend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendDir'; python server.py"

# Wait for backend
Write-Host "Waiting for backend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Load environment variables from .env file
$envFile = Join-Path $ProjectDir ".env"
$openrouterKey = ""
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^OPENROUTER_API_KEY=(.+)$') {
            $openrouterKey = $matches[1]
        }
    }
}

# Start LobeChat via Docker with same config as docker-compose.yml
Write-Host "Starting LobeChat frontend..." -ForegroundColor Green

$dockerCmd = @"
docker run -d ``
    --name lobe-chat ``
    -p 3210:3210 ``
    -e ENABLED_OPENAI=1 ``
    -e OPENAI_PROXY_URL=http://host.docker.internal:8000/v1 ``
    -e OPENAI_API_KEY=not-needed ``
    -e "OPENAI_MODEL_LIST=-all,+gpt-4o=gemini-3-flash" ``
    -e ENABLED_OLLAMA=0 ``
    -e "SYSTEM_AGENT=default=openai/gpt-4o,topic=openrouter/nvidia/nemotron-3-nano-30b-a3b:free,translation=openrouter/nvidia/nemotron-3-nano-30b-a3b:free" ``
    -e OPENROUTER_API_KEY=$openrouterKey ``
    -e ENABLED_OPENROUTER=1 ``
    -e "OPENROUTER_MODEL_LIST=-all,+nvidia/nemotron-3-nano-30b-a3b:free=Nemotron Nano (Free)" ``
    --add-host=host.docker.internal:host-gateway ``
    lobehub/lobe-chat:latest
"@

Invoke-Expression $dockerCmd

# Wait for LobeChat to be ready
Write-Host "Waiting for frontend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

$LocalIP = Get-LocalIP

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Lab Assistant is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Local access:" -ForegroundColor Cyan
Write-Host "  http://localhost:3210/chat" -ForegroundColor Yellow
Write-Host ""
Write-Host "Network access (other devices):" -ForegroundColor Cyan
Write-Host "  http://${LocalIP}:3210/chat" -ForegroundColor Yellow
Write-Host ""
Write-Host "Backend API:" -ForegroundColor Cyan
Write-Host "  http://${LocalIP}:8000" -ForegroundColor Yellow
Write-Host ""
Write-Host "----------------------------------------" -ForegroundColor Gray
Write-Host "To stop:" -ForegroundColor Cyan
Write-Host "  1. Close the backend PowerShell window" -ForegroundColor White
Write-Host "  2. Run: docker stop lobe-chat" -ForegroundColor White
Write-Host "----------------------------------------" -ForegroundColor Gray
Write-Host ""

# Auto-open the frontend in default browser
Write-Host "Opening frontend in browser..." -ForegroundColor Cyan
Start-Process "http://localhost:3210/chat"
