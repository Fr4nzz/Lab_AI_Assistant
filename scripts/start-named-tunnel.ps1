# Start Cloudflare Named Tunnel with Health Check and Auto-Restart
# This script runs a named tunnel (persistent URL) with health monitoring

param(
    [string]$CloudflaredPath = "cloudflared",
    [string]$TunnelName = "",
    [string]$LogFile = "logs\tunnel.log",
    [string]$UrlFile = "data\tunnel_url.txt",
    [string]$ConfigFile = "",
    [int]$MetricsPort = 20241,
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

# Clear log file on startup
if (Test-Path $LogFile) { Clear-Content -Path $LogFile -ErrorAction SilentlyContinue }

# Try to read tunnel config if not provided
$tunnelConfigFile = Join-Path $urlDir "tunnel_config.txt"
if (-not $TunnelName -and (Test-Path $tunnelConfigFile)) {
    Get-Content $tunnelConfigFile | ForEach-Object {
        if ($_ -match "^TUNNEL_NAME=(.+)$") { $TunnelName = $matches[1] }
    }
}

# Use default config file location if not specified
if (-not $ConfigFile) {
    $ConfigFile = Join-Path $env:USERPROFILE ".cloudflared\config.yml"
}

$restartCount = 0

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] $Message"
    Add-Content -Path $LogFile -Value $logEntry -ErrorAction SilentlyContinue
    Write-Host $logEntry
}

function Test-TunnelHealth {
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

function Get-TunnelUrl {
    # For named tunnels, read from config or tunnel_config.txt
    $hostname = ""

    # Try reading from tunnel_config.txt
    if (Test-Path $tunnelConfigFile) {
        Get-Content $tunnelConfigFile | ForEach-Object {
            if ($_ -match "^HOSTNAME=(.+)$") { $hostname = $matches[1] }
        }
    }

    # Try reading from config.yml
    if (-not $hostname -and (Test-Path $ConfigFile)) {
        Get-Content $ConfigFile | ForEach-Object {
            if ($_ -match "^\s*-\s*hostname:\s*(.+)$") { $hostname = $matches[1].Trim() }
        }
    }

    if ($hostname) {
        return "https://$hostname"
    }
    return $null
}

function Start-Tunnel {
    Write-Log "Starting named tunnel '$TunnelName' (metrics on port $MetricsPort)..."

    # Build arguments
    $arguments = @("tunnel")

    if ($TunnelName) {
        $arguments += @("run", $TunnelName)
    } else {
        # Use config file
        $arguments += "run"
    }

    # Start cloudflared
    $tempLog = [System.IO.Path]::GetTempFileName()
    $process = Start-Process -FilePath $CloudflaredPath `
        -ArgumentList $arguments `
        -PassThru -NoNewWindow -RedirectStandardError $tempLog

    # Wait for tunnel to be ready
    $elapsed = 0
    $maxWait = 30
    while ($elapsed -lt $maxWait -and -not $process.HasExited) {
        Start-Sleep -Milliseconds 500
        $elapsed += 0.5

        # Check if ready
        if (Test-TunnelHealth) {
            Write-Log "Tunnel is ready!"
            break
        }
    }

    # Get and save URL
    $tunnelUrl = Get-TunnelUrl
    if ($tunnelUrl) {
        [System.IO.File]::WriteAllText($UrlFile, $tunnelUrl)
        Write-Log "Tunnel URL: $tunnelUrl"
    } else {
        Write-Log "Warning: Could not determine tunnel URL"
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

# Validate configuration
if (-not (Test-Path $ConfigFile)) {
    Write-Log "ERROR: Config file not found: $ConfigFile"
    Write-Log "Please run cloudflare-tunnel-setup.bat first."
    exit 1
}

# Main restart loop
Write-Log "========================================="
Write-Log "Cloudflare Named Tunnel Service Starting"
Write-Log "Tunnel: $(if($TunnelName){$TunnelName}else{'(from config)'})"
Write-Log "Config: $ConfigFile"
Write-Log "Auto-restart enabled (MaxRestarts: $(if($MaxRestarts -eq -1){'unlimited'}else{$MaxRestarts}))"
Write-Log "Health check: every ${HealthCheckInterval}s, restart after ${HealthCheckFailures} failures"
Write-Log "========================================="

while ($true) {
    $tunnel = Start-Tunnel
    $process = $tunnel.Process
    $tempLog = $tunnel.TempLog

    if ($process -and -not $process.HasExited) {
        Write-Log "Tunnel running (PID: $($process.Id))"

        # Wait for tunnel to stabilize
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
                    if ($consecutiveFailures -gt 0) {
                        Write-Log "Tunnel health restored after $consecutiveFailures failures"
                    }
                    $consecutiveFailures = 0
                } else {
                    $consecutiveFailures++
                    Write-Log "Health check failed ($consecutiveFailures/$HealthCheckFailures)"

                    if ($consecutiveFailures -ge $HealthCheckFailures) {
                        Write-Log "Tunnel unhealthy - forcing restart..."
                        Stop-TunnelProcess -Process $process
                        break
                    }
                }
            }

            # Check temp log for critical errors
            if (Test-Path $tempLog) {
                $newContent = Get-Content $tempLog -Tail 5 -ErrorAction SilentlyContinue
                if ($newContent -match "ERR.*connection refused|ERR.*Failed to dial|ERR.*tunnel.*not found") {
                    Write-Log "Critical error detected in logs"
                    $consecutiveFailures = [Math]::Max($consecutiveFailures, $HealthCheckFailures - 1)
                }
            }
        }

        # Process exited or was killed
        $exitCode = if ($process.HasExited) { $process.ExitCode } else { -1 }
        Write-Log "Tunnel stopped (exit code: $exitCode)"

        # Clean up temp log
        if (Test-Path $tempLog) { Remove-Item $tempLog -Force -ErrorAction SilentlyContinue }

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
