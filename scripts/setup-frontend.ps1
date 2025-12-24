# Setup script for LobeChat frontend (Windows PowerShell)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Write-Host "Setting up LobeChat frontend..." -ForegroundColor Green

# Clone LobeChat if not exists
$FrontendDir = Join-Path $ProjectDir "frontend-lobechat"
if (-not (Test-Path $FrontendDir)) {
    Write-Host "Cloning LobeChat..." -ForegroundColor Yellow
    git clone https://github.com/lobehub/lobe-chat.git $FrontendDir
}

Set-Location $FrontendDir

# Create plugin directory
$PluginDir = Join-Path $FrontendDir "public\plugins\lab-assistant"
New-Item -ItemType Directory -Force -Path $PluginDir | Out-Null

# Copy plugin manifest
$ManifestContent = @'
{
  "$schema": "https://chat-plugins.lobehub.com/schema/manifest.json",
  "identifier": "lab-assistant",
  "version": "2.0.0",
  "type": "standalone",
  "api": [
    {
      "url": "http://localhost:8000/api/chat",
      "name": "sendMessage",
      "description": "Send a message to the lab assistant"
    },
    {
      "url": "http://localhost:8000/api/browser/screenshot",
      "name": "getScreenshot",
      "description": "Get current browser screenshot"
    }
  ],
  "meta": {
    "title": "Lab Assistant",
    "description": "Laboratory result entry assistant with browser automation",
    "tags": ["laboratory", "automation", "healthcare"]
  }
}
'@
Set-Content -Path (Join-Path $PluginDir "manifest.json") -Value $ManifestContent

# Create .env.local if not exists
$EnvFile = Join-Path $FrontendDir ".env.local"
if (-not (Test-Path $EnvFile)) {
    $EnvContent = @'
# Custom Backend (Lab Assistant API)
OPENAI_PROXY_URL=http://localhost:8000/v1
OPENAI_API_KEY=dummy-key-for-local
OPENAI_MODEL_LIST=+lab-assistant=Lab Assistant<100000:vision:fc>

# Google Gemini (add your key)
# GOOGLE_API_KEY=your-key-here

# Enable features
FEATURE_FLAGS={"enableArtifacts":true,"enablePlugins":true}
'@
    Set-Content -Path $EnvFile -Value $EnvContent
    Write-Host "Created .env.local - please add your API keys" -ForegroundColor Yellow
}

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    pnpm install
} elseif (Get-Command npm -ErrorAction SilentlyContinue) {
    npm install
} else {
    Write-Host "Please install pnpm or npm first" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Frontend setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To start the frontend:"
Write-Host "  cd frontend-lobechat; pnpm dev"
Write-Host ""
Write-Host "To start the backend:"
Write-Host "  cd backend; python server.py"
