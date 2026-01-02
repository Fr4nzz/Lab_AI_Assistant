# Start Cloudflare Quick Tunnel with Auto-Restart
# This script starts cloudflared and automatically restarts it on failure/network changes
param(
    [string]$CloudflaredPath = "cloudflared",
    [string]$LogFile = "logs\tunnel.log",
    [string]$UrlFile = "data\tunnel_url.txt",
    [int]$Port = 3000,
    [int]$Timeout = 30,
    [int]$MaxRestarts = -1,  # -1 = unlimited restarts
    [int]$RestartDelay = 5   # Seconds to wait before restart
)

# Ensure directories exist
$logDir = Split-Path $LogFile -Parent
$urlDir = Split-Path $UrlFile -Parent
if ($logDir -and -not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
if ($urlDir -and -not (Test-Path $urlDir)) { New-Item -ItemType Directory -Path $urlDir -Force | Out-Null }

$restartCount = 0

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] $Message"
    Add-Content -Path $LogFile -Value $logEntry -ErrorAction SilentlyContinue
    Write-Host $logEntry
}

function Start-Tunnel {
    # Remove old URL file (new URL will be generated)
    if (Test-Path $UrlFile) { Remove-Item $UrlFile -Force }

    Write-Log "Starting cloudflared tunnel to localhost:$Port..."

    # Start cloudflared with stderr going to a temp file for URL capture
    $tempLog = [System.IO.Path]::GetTempFileName()
    $process = Start-Process -FilePath $CloudflaredPath `
        -ArgumentList "tunnel", "--url", "http://localhost:$Port" `
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

    # Copy temp log to main log and continue appending
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
Write-Log "========================================="

while ($true) {
    $tunnel = Start-Tunnel
    $process = $tunnel.Process
    $tempLog = $tunnel.TempLog

    if ($process -and -not $process.HasExited) {
        Write-Log "Tunnel running (PID: $($process.Id))"

        # Monitor the process and stream logs
        while (-not $process.HasExited) {
            Start-Sleep -Seconds 2

            # Append any new log content
            if (Test-Path $tempLog) {
                $newContent = Get-Content $tempLog -Tail 10 -ErrorAction SilentlyContinue
                # Check for common error patterns that indicate we should restart
                if ($newContent -match "unreachable network|connection refused|i/o timeout") {
                    Write-Log "Network error detected, tunnel will restart when process exits"
                }
            }
        }

        # Process exited
        $exitCode = $process.ExitCode
        Write-Log "Tunnel exited with code: $exitCode"

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
