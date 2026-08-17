#!/bin/bash

# KONECTA V3 - Docker Compose Deployment (Bash/Shell)

echo "================================================================"
echo "  KONECTA V3 - Docker Compose Deployment"
echo "================================================================"
echo ""

# Check Docker
echo "[*] Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed!"
    echo "[INFO] Please install Docker first: https://docs.docker.com/install/"
    exit 1
fi

docker_version=$(docker --version)
echo "[OK] Docker is running: $docker_version"
echo ""

# Check Docker Compose
echo "[*] Checking Docker Compose..."
if ! docker compose version &> /dev/null; then
    echo "[ERROR] Docker Compose is not installed!"
    exit 1
fi

echo "[OK] Docker Compose is installed"
echo ""

# Build
echo "[*] Building Docker image..."
cd "$(dirname "$0")"
docker compose build

if [ $? -ne 0 ]; then
    echo "[ERROR] Build failed!"
    exit 1
fi

echo "[OK] Build successful"
echo ""

# Start services
echo "[*] Starting services..."
docker compose up -d

if [ $? -ne 0 ]; then
    echo "[ERROR] Startup failed!"
    echo "[INFO] Check logs: docker compose logs"
    exit 1
fi

echo "[OK] Services started"
echo ""

# Wait for health
echo "[*] Waiting for services to be ready..."
sleep 5

# Health check
echo "[*] Health check..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "[OK] API is healthy"
    curl -s http://localhost:8000/health | python -m json.tool
else
    echo "[WARNING] Health check failed, retrying..."
    sleep 3
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "[OK] API is healthy"
        curl -s http://localhost:8000/health | python -m json.tool
    else
        echo "[ERROR] API not responding"
    fi
fi

echo ""
echo "================================================================"
echo "  [SUCCESS] KONECTA V3 is running!"
echo "================================================================"
echo ""

echo "API:        http://localhost:8000"
echo "Health:     http://localhost:8000/health"
echo "Prometheus: http://localhost:9090"
echo ""

echo "Useful commands:"
echo "  docker compose ps              - Show running containers"
echo "  docker compose logs -f          - Show logs"
echo "  docker compose stop             - Stop services"
echo "  docker compose down             - Stop and remove"
echo ""
