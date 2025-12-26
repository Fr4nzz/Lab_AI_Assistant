# Restart Docker containers for Lab AI Assistant (docker-compose)
# NOTE: This runs BOTH backend and frontend in Docker
# For development with local backend (recommended), use: .\scripts\start-docker.ps1
#
# Usage: .\restart.ps1 [frontend|backend|all]

param(
    [string]$Service = "all"
)

# Get all network adapters with their IPs (for display)
function Get-NetworkIPs {
    $adapters = @()
    Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '127.*' } |
        ForEach-Object {
            $alias = $_.InterfaceAlias
            $ip = $_.IPAddress
            $category = "Other"
            $priority = 99
            if ($alias -match 'Wi-Fi|Wireless|WLAN') { $category = "Wi-Fi"; $priority = 1 }
            elseif ($alias -match '^Ethernet' -and $alias -notmatch 'VMware|VirtualBox|vEthernet|Hyper-V') { $category = "Ethernet"; $priority = 2 }
            elseif ($alias -match 'VMware|VirtualBox') { $category = "Virtual (VM)"; $priority = 50 }
            elseif ($alias -match 'vEthernet|WSL|Hyper-V') { $category = "Virtual (WSL/Hyper-V)"; $priority = 51 }
            $adapters += [PSCustomObject]@{ Alias = $alias; IP = $ip; Category = $category; Priority = $priority }
        }
    return $adapters | Sort-Object Priority
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

$NetworkAdapters = Get-NetworkIPs

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Lab Assistant is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Local access:" -ForegroundColor Cyan
Write-Host "  http://localhost:3210/chat" -ForegroundColor Yellow
Write-Host ""
Write-Host "Network access (other devices):" -ForegroundColor Cyan

$shownAdapters = $NetworkAdapters | Where-Object { $_.Priority -le 10 }
if ($shownAdapters) {
    foreach ($adapter in $shownAdapters) {
        Write-Host "  [$($adapter.Category)] http://$($adapter.IP):3210/chat" -ForegroundColor Yellow
    }
} else {
    $firstIP = ($NetworkAdapters | Select-Object -First 1).IP
    if ($firstIP) { Write-Host "  http://${firstIP}:3210/chat" -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "Clear browser cache (Ctrl+Shift+Delete) if needed" -ForegroundColor Gray
