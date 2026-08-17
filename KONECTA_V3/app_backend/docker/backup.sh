#!/bin/sh
# KONECTA backend — database backup script
#
# Suporta SQLite (online backup, WAL-safe) e PostgreSQL (pg_dump -Fc).
# Retenção configurável via BACKUP_RETENTION_DAYS (default 14).
#
# Uso (dentro do container ou no host):
#   ENVIRONMENT=production DATABASE_URL=postgresql+psycopg2://... ./backup.sh
#   ENVIRONMENT=development ./backup.sh
#
# Recomendado via cron/Task Scheduler:
#   0 2 * * * /app/app_backend/docker/backup.sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-/app/app_backend/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
DATABASE_URL="${DATABASE_URL:-}"
STAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q "^postgres"; then
    # --- PostgreSQL ------------------------------------------------------
    # Extrai host/porta/db/user/pass da URL para o pg_dump (PG* env vars).
    # Ex.: postgresql+psycopg2://user:pass@host:5432/konecta
    URL="${DATABASE_URL#*://}"
    CREDS="${URL%%@*}"
    HOSTPORT="${URL#*@}"
    HOSTPORT="${HOSTPORT%%/*}"
    HOST="${HOSTPORT%%:*}"
    PORT="${HOSTPORT##*:}"
    DB="${URL##*/}"
    DB="${DB%%\?*}"
    USER="${CREDS%%:*}"
    PASS="${CREDS#*:}"

    export PGHOST="${HOST:-localhost}" PGPORT="${PORT:-5432}" PGUSER="${USER:-konecta}" PGPASSWORD="${PASS:-}"
    FILE="$BACKUP_DIR/konecta_pg_${STAMP}.dump"

    echo "[backup] pg_dump -> $FILE"
    pg_dump -Fc -d "${DB}" -f "$FILE"
else
    # --- SQLite (online backup via sqlite3/API, seguro com WAL) ----------
    DB_FILE="${SQLITE_DB_FILE:-/app/app_backend/data/konecta.db}"
    FILE="$BACKUP_DIR/konecta_sqlite_${STAMP}.db"
    echo "[backup] sqlite online backup -> $FILE"
    if command -v sqlite3 >/dev/null 2>&1; then
        sqlite3 "$DB_FILE" ".backup '$FILE'"
    else
        python -c "
import sqlite3, sys
src = sqlite3.connect('$DB_FILE')
dst = sqlite3.connect('$FILE')
src.backup(dst)
dst.close(); src.close()
print('[backup] sqlite backup ok')
"
    fi
fi

# --- Retenção ---------------------------------------------------------------
echo "[backup] prunando arquivos mais antigos que ${RETENTION_DAYS} dias"
find "$BACKUP_DIR" -type f \( -name 'konecta_*.db' -o -name 'konecta_*.dump' \) \
    -mtime "+${RETENTION_DAYS}" -delete

echo "[backup] done: $FILE"
