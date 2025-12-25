# Restart Docker containers for Lab AI Assistant (docker-compose)
# NOTE: This runs BOTH backend and frontend in Docker
# For development with local backend (recommended), use: .\scripts\start-docker.ps1
#
# Usage: .\restart.ps1 [frontend|backend|all]

param(
    [string]$Service = "all"
)

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

Write-Host "Stopping containers..." -ForegroundColor Yellow

if ($Service -eq "all") {
    docker-compose down
    docker network prune -f
    Write-Host "Starting all services..." -ForegroundColor Green
    docker-compose up -d
} else {
    docker-compose stop $Service
    docker-compose rm -f $Service
    Write-Host "Starting $Service..." -ForegroundColor Green
    docker-compose up -d $Service
}

Write-Host ""
Write-Host "Container status:" -ForegroundColor Cyan
docker-compose ps

$LocalIP = Get-LocalIP

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Lab Assistant is running!" -ForegroundColor Green
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
Write-Host "Clear browser cache (Ctrl+Shift+Delete) if needed" -ForegroundColor Gray
