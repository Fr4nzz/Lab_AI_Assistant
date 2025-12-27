# Lab AI Assistant - Development Startup Script
# Starts both backend and frontend with proper network detection

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Continue"

# Get all network adapters with their IPs (for display)
function Get-NetworkIPs {
    $adapters = @()

    # Get all IPv4 addresses that are connected
    Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '127.*' } |
        ForEach-Object {
            $alias = $_.InterfaceAlias
            $ip = $_.IPAddress

            # Categorize adapters
            $category = "Other"
            $priority = 99

            if ($alias -match 'Wi-Fi|Wireless|WLAN') {
                $category = "Wi-Fi"
                $priority = 1
            } elseif ($alias -match '^Ethernet' -and $alias -notmatch 'VMware|VirtualBox|vEthernet|Hyper-V') {
                $category = "Ethernet"
                $priority = 2
            } elseif ($alias -match 'VMware|VirtualBox') {
                $category = "Virtual (VM)"
                $priority = 50
            } elseif ($alias -match 'vEthernet|WSL|Hyper-V') {
                $category = "Virtual (WSL/Hyper-V)"
                $priority = 51
            } elseif ($alias -match 'Bluetooth') {
                $category = "Bluetooth"
                $priority = 60
            }

            $adapters += [PSCustomObject]@{
                Alias = $alias
                IP = $ip
                Category = $category
                Priority = $priority
            }
        }

    # Sort by priority (Wi-Fi and Ethernet first)
    return $adapters | Sort-Object Priority
}

# Display header
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Lab AI Assistant - Development" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get network adapters
$NetworkAdapters = Get-NetworkIPs

# Start backend
if (-not $FrontendOnly) {
    Write-Host "Starting Backend (Python)..." -ForegroundColor Yellow
    $backendPath = Join-Path $PSScriptRoot "backend"

    # Start backend in new window
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; python server.py" -WorkingDirectory $backendPath

    Write-Host "Backend starting in new window..." -ForegroundColor Green
    Start-Sleep -Seconds 2
}

# Start frontend
if (-not $BackendOnly) {
    Write-Host "Starting Frontend (Next.js)..." -ForegroundColor Yellow
    $frontendPath = Join-Path $PSScriptRoot "frontend"

    # Start frontend in new window
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev" -WorkingDirectory $frontendPath

    Write-Host "Frontend starting in new window..." -ForegroundColor Green
    Start-Sleep -Seconds 3
}

# Display access information
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Lab AI Assistant Ready!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Local access:" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Yellow
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Yellow
Write-Host ""
Write-Host "Network access (other devices):" -ForegroundColor Cyan

# Show only Wi-Fi and Ethernet adapters (the likely ones for other devices)
$shownAdapters = $NetworkAdapters | Where-Object { $_.Priority -le 10 }

if ($shownAdapters) {
    foreach ($adapter in $shownAdapters) {
        $ip = $adapter.IP
        $category = $adapter.Category
        Write-Host "  [$category] Frontend: http://${ip}:3000" -ForegroundColor Yellow
        Write-Host "  [$category] Backend:  http://${ip}:8000" -ForegroundColor Gray
    }
} else {
    # Fallback: show first available IP if no Wi-Fi/Ethernet found
    $firstIP = ($NetworkAdapters | Select-Object -First 1).IP
    if ($firstIP) {
        Write-Host "  Frontend: http://${firstIP}:3000" -ForegroundColor Yellow
        Write-Host "  Backend:  http://${firstIP}:8000" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "----------------------------------------" -ForegroundColor Gray
Write-Host "To stop: Close the terminal windows" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Gray
Write-Host ""
