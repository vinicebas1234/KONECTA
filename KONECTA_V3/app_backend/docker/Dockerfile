# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# System deps (psycopg2 needs libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install backend requirements first (cache layer)
COPY app_backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

# Copy package
COPY app_backend ./app_backend
# Minimal package marker so `import app_backend` works with PYTHONPATH=/app
# (repo layout: /app/app_backend/...)

ENV PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=8000

RUN chmod +x /app/app_backend/docker/entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

ENTRYPOINT ["/app/app_backend/docker/entrypoint.sh"]
CMD ["uvicorn", "app_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
