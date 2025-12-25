# Lab Assistant AI - Setup Script for Windows
# Run this script in PowerShell: .\setup.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Lab Assistant AI - Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "[1/4] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "      Please edit .env and add your GEMINI_API_KEYS" -ForegroundColor Red
    Write-Host "      Get keys from: https://aistudio.google.com/apikey" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "[1/4] .env file already exists" -ForegroundColor Green
}

# Check if Python venv exists
if (-not (Test-Path ".venv")) {
    Write-Host "[2/4] Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "[2/4] Virtual environment already exists" -ForegroundColor Green
}

# Activate venv and install dependencies
Write-Host "[3/4] Installing Python dependencies..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt --quiet

# Check if Docker is available
$dockerAvailable = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "IMPORTANT: Edit .env and add your API keys:" -ForegroundColor Yellow
Write-Host "  - GEMINI_API_KEYS (required)" -ForegroundColor White
Write-Host "  - OPENROUTER_API_KEY (optional, for topic naming)" -ForegroundColor White
Write-Host ""

if ($dockerAvailable) {
    Write-Host "To start with Docker (recommended):" -ForegroundColor Cyan
    Write-Host "  docker-compose up -d" -ForegroundColor White
    Write-Host ""
    Write-Host "Then open: http://localhost:3210" -ForegroundColor White
} else {
    Write-Host "Docker not found. To run locally:" -ForegroundColor Cyan
    Write-Host "  1. Start backend:  cd backend && python server.py" -ForegroundColor White
    Write-Host "  2. Install Docker and run LobeChat:" -ForegroundColor White
    Write-Host "     docker run -d -p 3210:3210 lobehub/lobe-chat:latest" -ForegroundColor White
}

Write-Host ""
Write-Host "For more info, see README.md" -ForegroundColor Gray
