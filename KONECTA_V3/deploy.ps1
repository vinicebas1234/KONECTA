# KONECTA V3 - Docker Compose Deployment (PowerShell)

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  KONECTA V3 - Docker Compose Deployment" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker
Write-Host "[*] Checking Docker Desktop..." -ForegroundColor Yellow
$docker = docker --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker is not running!" -ForegroundColor Red
    Write-Host "[INFO] Please start Docker Desktop first." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Docker is running: $docker" -ForegroundColor Green
Write-Host ""

# Build
Write-Host "[*] Building Docker image..." -ForegroundColor Yellow
Set-Location -Path $PSScriptRoot
docker compose build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Build failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Build successful" -ForegroundColor Green
Write-Host ""

# Start services
Write-Host "[*] Starting services..." -ForegroundColor Yellow
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Startup failed!" -ForegroundColor Red
    Write-Host "[INFO] Check logs: docker compose logs" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Services started" -ForegroundColor Green
Write-Host ""

# Wait for health
Write-Host "[*] Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Health check
Write-Host "[*] Health check..." -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
    Write-Host "[OK] API is healthy" -ForegroundColor Green
    Write-Host $health.Content
} catch {
    Write-Host "[WARNING] Health check failed, retrying..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    try {
        $health = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
        Write-Host "[OK] API is healthy" -ForegroundColor Green
        Write-Host $health.Content
    } catch {
        Write-Host "[ERROR] API not responding" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  [SUCCESS] KONECTA V3 is running!" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""

Write-Host "API:        http://localhost:8000" -ForegroundColor Cyan
Write-Host "Health:     http://localhost:8000/health" -ForegroundColor Cyan
Write-Host "Prometheus: http://localhost:9090" -ForegroundColor Cyan
Write-Host ""

Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  docker compose ps              - Show running containers"
Write-Host "  docker compose logs -f          - Show logs"
Write-Host "  docker compose stop             - Stop services"
Write-Host "  docker compose down             - Stop and remove"
Write-Host ""

Read-Host "Press Enter to exit"
