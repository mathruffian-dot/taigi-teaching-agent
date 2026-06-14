# Taigi Teaching Agent Environment Setup Script (setup.ps1)
$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Green
Write-Host "Initializing Taigi Teaching Agent Project..." -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green

# 1. Check Python
Write-Host "[1/5] Checking Python environment..." -ForegroundColor Yellow
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonVersion = python --version
    Write-Host "  Found Python: $pythonVersion" -ForegroundColor Green
} else {
    Write-Error "Python not found. Please install Python (suggested >= 3.10) and add it to PATH."
}

# 2. Check virtual environment .venv
Write-Host "[2/5] Setting up Python virtual environment (.venv)..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "  .venv already exists, skipping creation." -ForegroundColor Green
} else {
    python -m venv .venv
    Write-Host "  Successfully created .venv." -ForegroundColor Green
}

# 3. Install dependencies
Write-Host "[3/5] Installing dependencies (requirements.txt)..." -ForegroundColor Yellow
& .venv/Scripts/pip install --upgrade pip
& .venv/Scripts/pip install -r requirements.txt
Write-Host "  All dependencies installed successfully." -ForegroundColor Green

# 4. Copy config
Write-Host "[4/5] Initializing configuration file..." -ForegroundColor Yellow
if (Test-Path "config.json") {
    Write-Host "  config.json already exists, skipping." -ForegroundColor Green
} else {
    Copy-Item "config.example.json" "config.json"
    Write-Host "  Created config.json from config.example.json." -ForegroundColor Green
}

# 5. Check Ollama
Write-Host "[5/5] Checking local Ollama service status..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 3
    Write-Host "  Ollama service is ONLINE." -ForegroundColor Green
    
    $models = $response.models.name
    Write-Host "  Available Ollama models: $($models -join ', ')" -ForegroundColor Green
} catch {
    Write-Host "  Note: Local Ollama service is not running or not accessible." -ForegroundColor Cyan
}

Write-Host "==================================================" -ForegroundColor Green
Write-Host "Environment setup completed successfully!" -ForegroundColor Green
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Activate virtual environment: .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "2. Edit config.json with your settings." -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Green
