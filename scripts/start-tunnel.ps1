# Start Cloudflare Quick Tunnel with Health Check and Auto-Restart
# This script starts cloudflared with metrics endpoint and monitors health
# Automatically restarts when tunnel connection is lost

param(
    [string]$CloudflaredPath = "cloudflared",
    [string]$LogFile = "logs\tunnel.log",
    [string]$UrlFile = "data\tunnel_url.txt",
    [int]$Port = 3000,
    [int]$MetricsPort = 20241,
    [int]$Timeout = 30,
    [int]$MaxRestarts = -1,  # -1 = unlimited restarts
    [int]$RestartDelay = 5,  # Seconds to wait before restart
    [int]$HealthCheckInterval = 10,  # Seconds between health checks
    [int]$HealthCheckFailures = 3    # Consecutive failures before restart
)

# Ensure directories exist
$logDir = Split-Path $LogFile -Parent
$urlDir = Split-Path $UrlFile -Parent
if ($logDir -and -not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
if ($urlDir -and -not (Test-Path $urlDir)) { New-Item -ItemType Directory -Path $urlDir -Force | Out-Null }

# Clear log file on startup (fresh log each restart, like other services)
if (Test-Path $LogFile) { Clear-Content -Path $LogFile -ErrorAction SilentlyContinue }

$restartCount = 0

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] $Message"
    Add-Content -Path $LogFile -Value $logEntry -ErrorAction SilentlyContinue
    Write-Host $logEntry
}

function Test-TunnelHealth {
    # Check the /ready endpoint on the metrics server
    # Returns $true if healthy, $false otherwise
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$MetricsPort/ready" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Stop-TunnelProcess {
    param([System.Diagnostics.Process]$Process)

    if ($Process -and -not $Process.HasExited) {
        Write-Log "Stopping tunnel process (PID: $($Process.Id))..."
        try {
            $Process.Kill()
            $Process.WaitForExit(5000)
        } catch {
            Write-Log "Warning: Could not kill process gracefully"
        }
    }
}

function Start-Tunnel {
    # Remove old URL file (new URL will be generated)
    if (Test-Path $UrlFile) { Remove-Item $UrlFile -Force }

    Write-Log "Starting cloudflared tunnel to localhost:$Port (metrics on port $MetricsPort)..."

    # Start cloudflared with metrics endpoint enabled
    $tempLog = [System.IO.Path]::GetTempFileName()
    $process = Start-Process -FilePath $CloudflaredPath `
        -ArgumentList "tunnel", "--url", "http://localhost:$Port", "--metrics", "127.0.0.1:$MetricsPort" `
        -PassThru -NoNewWindow -RedirectStandardError $tempLog

    # Wait for URL to appear
    $elapsed = 0
    $urlFound = $false
    while ($elapsed -lt $Timeout -and -not $process.HasExited) {
        Start-Sleep -Milliseconds 500
        $elapsed += 0.5

        if (Test-Path $tempLog) {
            $content = Get-Content $tempLog -Raw -ErrorAction SilentlyContinue
            if ($content -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
                $tunnelUrl = $matches[0]
                [System.IO.File]::WriteAllText($UrlFile, $tunnelUrl)
                Write-Log "Tunnel URL: $tunnelUrl"
                $urlFound = $true
                break
            }
        }
    }

    if (-not $urlFound -and -not $process.HasExited) {
        Write-Log "Warning: Could not capture tunnel URL within ${Timeout}s"
    }

    # Copy temp log to main log
    if (Test-Path $tempLog) {
        Get-Content $tempLog | Add-Content -Path $LogFile -ErrorAction SilentlyContinue
    }

    return @{
        Process = $process
        TempLog = $tempLog
    }
}

# Main restart loop
Write-Log "========================================="
Write-Log "Cloudflare Tunnel Service Starting"
Write-Log "Auto-restart enabled (MaxRestarts: $(if($MaxRestarts -eq -1){'unlimited'}else{$MaxRestarts}))"
Write-Log "Health check: every ${HealthCheckInterval}s, restart after ${HealthCheckFailures} failures"
Write-Log "========================================="

while ($true) {
    $tunnel = Start-Tunnel
    $process = $tunnel.Process
    $tempLog = $tunnel.TempLog

    if ($process -and -not $process.HasExited) {
        Write-Log "Tunnel running (PID: $($process.Id))"

        # Wait for metrics server to be ready
        Start-Sleep -Seconds 3

        $consecutiveFailures = 0
        $lastHealthCheck = Get-Date

        # Monitor the process with active health checking
        while (-not $process.HasExited) {
            Start-Sleep -Seconds 1

            # Check health at intervals
            $now = Get-Date
            if (($now - $lastHealthCheck).TotalSeconds -ge $HealthCheckInterval) {
                $lastHealthCheck = $now

                if (Test-TunnelHealth) {
                    # Healthy - reset failure counter
                    if ($consecutiveFailures -gt 0) {
                        Write-Log "Tunnel health restored after $consecutiveFailures failures"
                    }
                    $consecutiveFailures = 0
                } else {
                    # Unhealthy
                    $consecutiveFailures++
                    Write-Log "Health check failed ($consecutiveFailures/$HealthCheckFailures)"

                    if ($consecutiveFailures -ge $HealthCheckFailures) {
                        Write-Log "Tunnel unhealthy - forcing restart..."
                        Stop-TunnelProcess -Process $process
                        break
                    }
                }
            }

            # Also check temp log for critical errors
            if (Test-Path $tempLog) {
                $newContent = Get-Content $tempLog -Tail 5 -ErrorAction SilentlyContinue
                if ($newContent -match "ERR.*unreachable network|ERR.*connection refused|ERR.*Failed to dial") {
                    Write-Log "Critical network error detected in logs"
                    # Don't immediately restart - let health check handle it
                    # But increment failure counter to speed up detection
                    $consecutiveFailures = [Math]::Max($consecutiveFailures, $HealthCheckFailures - 1)
                }
            }
        }

        # Process exited or was killed
        $exitCode = if ($process.HasExited) { $process.ExitCode } else { -1 }
        Write-Log "Tunnel stopped (exit code: $exitCode)"

        # Clean up temp log
        if (Test-Path $tempLog) { Remove-Item $tempLog -Force -ErrorAction SilentlyContinue }

        # Clear URL file since tunnel is down
        if (Test-Path $UrlFile) { Remove-Item $UrlFile -Force -ErrorAction SilentlyContinue }

    } else {
        Write-Log "Failed to start tunnel process"
    }

    # Check restart limit
    $restartCount++
    if ($MaxRestarts -ne -1 -and $restartCount -ge $MaxRestarts) {
        Write-Log "Max restart limit ($MaxRestarts) reached. Exiting."
        break
    }

    # Wait before restart with exponential backoff (max 60 seconds)
    $delay = [Math]::Min($RestartDelay * [Math]::Pow(1.5, [Math]::Min($restartCount - 1, 5)), 60)
    Write-Log "Restarting in $([Math]::Round($delay, 1)) seconds... (restart #$restartCount)"
    Start-Sleep -Seconds $delay
}

Write-Log "Tunnel service stopped."
