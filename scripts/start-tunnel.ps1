# Start Cloudflare Quick Tunnel
# This script starts cloudflared and captures the tunnel URL to a file
param(
    [string]$CloudflaredPath = "cloudflared",
    [string]$LogFile = "logs\tunnel.log",
    [string]$UrlFile = "data\tunnel_url.txt",
    [int]$Port = 3000,
    [int]$Timeout = 30
)

# Ensure directories exist
$logDir = Split-Path $LogFile -Parent
$urlDir = Split-Path $UrlFile -Parent
if ($logDir -and -not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
if ($urlDir -and -not (Test-Path $urlDir)) { New-Item -ItemType Directory -Path $urlDir -Force | Out-Null }

# Remove old URL file
if (Test-Path $UrlFile) { Remove-Item $UrlFile -Force }

# Start cloudflared
$process = Start-Process -FilePath $CloudflaredPath `
    -ArgumentList "tunnel", "--url", "http://localhost:$Port" `
    -PassThru -NoNewWindow -RedirectStandardError $LogFile

# Wait for URL to appear in log
$elapsed = 0
while ($elapsed -lt $Timeout -and -not $process.HasExited) {
    Start-Sleep -Milliseconds 500
    $elapsed += 0.5

    if (Test-Path $LogFile) {
        $content = Get-Content $LogFile -Raw -ErrorAction SilentlyContinue
        if ($content -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
            [System.IO.File]::WriteAllText($UrlFile, $matches[0])
            break
        }
    }
}

# Keep running until cloudflared exits
if (-not $process.HasExited) {
    Wait-Process -Id $process.Id -ErrorAction SilentlyContinue
}
