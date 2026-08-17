#!/bin/sh
set -e

echo "[entrypoint] KONECTA backend starting..."
echo "[entrypoint] ENVIRONMENT=${ENVIRONMENT:-development}"

# Garante diretórios de runtime
mkdir -p /app/app_backend/data /app/app_backend/logs /app/app_backend/backups

# Migrations (Alembic) — falha o container se migration quebrada
cd /app/app_backend
if command -v alembic >/dev/null 2>&1; then
  echo "[entrypoint] Running alembic upgrade head..."
  alembic upgrade head || {
    echo "[entrypoint] WARN: alembic falhou; tentando init_db via Python..."
    python -c "from app_backend.database import init_db; init_db()"
  }
else
  echo "[entrypoint] alembic não encontrado; init_db via Python"
  python -c "from app_backend.database import init_db; init_db()"
fi

cd /app
echo "[entrypoint] Exec: $*"
exec "$@"
