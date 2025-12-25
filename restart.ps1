# Restart Docker containers for Lab AI Assistant
# Usage: .\restart.ps1 [frontend|backend|all]

param(
    [string]$Service = "all"
)

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

Write-Host ""
Write-Host "Done! Clear browser cache (Ctrl+Shift+Delete) and refresh localhost:3210" -ForegroundColor Green
