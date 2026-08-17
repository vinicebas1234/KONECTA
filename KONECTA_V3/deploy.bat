@echo off
cls
echo ================================================================
echo  KONECTA V3 - Docker Compose Deployment
echo ================================================================
echo.

REM Check Docker
echo [*] Checking Docker Desktop...
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not running!
    echo [INFO] Please start Docker Desktop first.
    pause
    exit /b 1
)

echo [OK] Docker is running
echo.

REM Build
echo [*] Building Docker image...
cd /d "%~dp0"
docker compose build

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo [OK] Build successful
echo.

REM Start services
echo [*] Starting services...
docker compose up -d

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Startup failed!
    echo [INFO] Check logs: docker compose logs
    pause
    exit /b 1
)

echo [OK] Services started
echo.

REM Wait for health
echo [*] Waiting for services to be ready...
timeout /t 5 /nobreak

REM Health check
echo [*] Health check...
curl -s http://localhost:8000/health >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Health check failed, waiting...
    timeout /t 5 /nobreak
    curl -s http://localhost:8000/health
)

echo.
echo ================================================================
echo  [SUCCESS] KONECTA V3 is running!
echo ================================================================
echo.
echo API:        http://localhost:8000
echo Health:     http://localhost:8000/health
echo Prometheus: http://localhost:9090
echo.
echo Useful commands:
echo   docker compose ps              - Show running containers
echo   docker compose logs -f          - Show logs
echo   docker compose stop             - Stop services
echo   docker compose down             - Stop and remove
echo.
pause
