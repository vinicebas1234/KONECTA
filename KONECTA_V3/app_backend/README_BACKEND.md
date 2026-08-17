# KONECTA V3 — Backend API

API/storage layer for the KONECTA Intelligence Hub (Libras recognition).  
**No ML/recognition logic here** — only REST endpoints, persistence, auth, and ops.

Stack: **FastAPI · SQLAlchemy 2 · Alembic · SQLite (dev) / PostgreSQL (prod)**

---

## Quick start (local)

From the **repo root** (`KONECTA_V3/`):

```bash
# 1. Create/activate venv (if needed)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# 2. Install backend deps
pip install -r app_backend/requirements.txt

# 3. Env file
copy app_backend\.env.example app_backend\.env
# (or: cp app_backend/.env.example app_backend/.env)

# 4. Migrate (optional — startup also runs create_all + seed)
cd app_backend
alembic upgrade head
cd ..

# 5. Run
uvicorn app_backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open: http://localhost:8000/docs · Health: http://localhost:8000/api/health

### Tests

```bash
pytest app_backend/tests -v   # 13 tests: health, auth, metrics, webhook, signals, /metrics
```

### Docker

```bash
cd app_backend
docker compose up --build
```

Compose lives at `app_backend/docker-compose.yml`. From repo root:

```bash
docker compose -f app_backend/docker-compose.yml up --build
```

Default uses **SQLite** on a named volume. Uncomment the `postgres` service in `docker-compose.yml` and set `DATABASE_URL` for production.

---

## API overview

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | Public | Status, DB ping, version, uptime, perf snapshot |
| POST | `/api/metrics` | **X-API-Key** | Ingest performance/business metrics |
| GET | `/api/signals?user_id=` | Optional key | List recognized signals |
| GET | `/api/models/available` | Public | List available ML models |
| POST | `/api/webhook/signal-recognized` | **X-API-Key** | N8N webhook — persist a recognition event |
| GET | `/metrics` | Public | Prometheus metrics (text format) |
| GET | `/health` | Public | Legacy health (`check_db_health`) — old contract |

Versioning: all routes under `/api/` prefix (backward-compatible surface).

### Examples

```bash
# Health
curl http://localhost:8000/api/health

# Models
curl http://localhost:8000/api/models/available

# Webhook (N8N)
curl -X POST http://localhost:8000/api/webhook/signal-recognized \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-konecta-api-key-change-me" \
  -d "{\"user_id\":\"11111111-1111-4111-8111-111111111111\",\"signal_label\":\"OLA\",\"confidence\":0.95,\"latency_ms\":42,\"model_used\":\"konecta_v3\"}"

# Metrics
curl -X POST http://localhost:8000/api/metrics \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-konecta-api-key-change-me" \
  -d "{\"name\":\"inference_latency_ms\",\"value\":42,\"tags\":{\"source\":\"n8n\"}}"

# Signals for a user
curl "http://localhost:8000/api/signals?user_id=11111111-1111-4111-8111-111111111111"
```

---

## Auth

- Header: **`X-API-Key`**
- Env: **`KONECTA_API_KEY`** (default in `.env.example` is for local/dev only)
- Extra keys: `API_KEYS=key2,key3` (CSV)
- Protected: `POST /api/metrics`, `POST /api/webhook/signal-recognized`
- Public: health, models; signals accept an optional key (invalid key → 401)

Rotate keys in production and never commit real secrets.

---

## Rate limiting

- Default: **`RATE_LIMIT=100/minute`** (env, e.g. `RATE_LIMIT=3/minute`)
- Enforced by an in-memory **token bucket** middleware (`middleware/rate_limit.py`), keyed by API key (first 16 chars) or client IP; thread-safe via `threading.Lock`
- Exempt: `/api/health`, `/health`, `/docs`, `/openapi.json`, `/redoc`, `/metrics` and `OPTIONS` preflight
- On limit: `429` with `X-RateLimit-Limit` / `X-RateLimit-Remaining` headers
- **Why not slowapi as default?** slowapi's `SlowAPIMiddleware` is a no-op on this stack (FastAPI 0.141 / modern Starlette): included routers surface as `_IncludedRouter` without `.endpoint`, so `_find_route_handler` returns `None` and every route is treated as exempt. The token bucket is reliable; use slowapi only for explicit per-route `@limiter.limit(...)` decorators.
- Multi-instance prod: move to Redis-backed limiting (or the gateway) — per-process bucket does not scale across workers.

---

## Database & migrations

### Schema

| Table | Purpose |
|-------|---------|
| `users` | id (UUID str), username, email, api_key_hash, is_active, timestamps |
| `signals` | recognition events; indexes on `user_id`, `created_at`, `signal_label`, `(user_id, created_at)` |
| `ml_models` | available models; unique `(name, version)` |

### Seed

On startup (and in migration `001_initial_schema`) the model **`konecta_v3` / `v1`** is ensured available.

### Alembic

```bash
cd app_backend
alembic upgrade head          # apply
alembic revision -m "msg"    # new revision (edit manually or --autogenerate)
alembic downgrade -1         # rollback one
```

`migrations/env.py` reads `DATABASE_URL` from Settings (`.env`).

### SQLite vs PostgreSQL

| | Dev | Prod |
|--|-----|------|
| URL | `sqlite:///./data/konecta.db` | `postgresql+psycopg2://user:pass@host:5432/konecta` |
| Notes | WAL enabled, file under `app_backend/data/` | connection pool + `pool_pre_ping` |

---

## Backup strategy

### SQLite (dev / small deploy)

1. Prefer **online backup** while WAL is on:
   ```bash
   # From app_backend/
   python -c "import sqlite3; src=sqlite3.connect('data/konecta.db'); dst=sqlite3.connect('backups/konecta-$(date +%Y%m%d).db'); src.backup(dst); dst.close(); src.close()"
   ```
   Windows PowerShell: copy `data\konecta.db` (+ `-wal`/`-shm` if present) into `backups\` with a timestamp.
2. Retention: keep **`BACKUP_RETENTION_DAYS`** (default 14); prune older files via cron/Task Scheduler.
3. Store backups off-box (S3/Azure Blob) for anything beyond local experiments.

### PostgreSQL (prod)

1. Nightly `pg_dump -Fc` (or managed backup / PITR on the cloud provider).
2. Test restore quarterly (`pg_restore` into a staging instance).
3. Before major migrations: take a dump + verify `alembic current`.

### What to back up

- Database file / dump
- `.env` secrets (vault — not in git)
- Model artifacts referenced by `ml_models.path` (outside this API package)

---

## Logging & monitoring

- **Structured JSON logs** to stdout + `app_backend/logs/app_backend.log`
- Each request gets **`X-Request-ID`**, method, path, status, `latency_ms`
- **Error tracking hook**: `report_error()` logs JSON; if `SENTRY_DSN` is set, forwards to Sentry
- **Prometheus**: `GET /metrics` exposes `konecta_http_requests_total` and `konecta_http_request_duration_seconds` (`PROMETHEUS_ENABLED=true`)
- **Health**: `GET /api/health` → `status`, `db`, `version`, `uptime_seconds`, `performance` snapshot
- **Legacy**: `GET /health` → `status`/`db` (old contract used by the repo's compose healthcheck)

---

## CORS

`CORS_ORIGINS` (CSV). Defaults include localhost:3000, 5173, 8000.  
Configure production front-end origins explicitly; avoid `*` with credentials.

---

## Production checklist

- [ ] Set strong unique `KONECTA_API_KEY` (and rotate)
- [ ] `ENVIRONMENT=production`, `DEBUG=false`
- [ ] Use PostgreSQL `DATABASE_URL`; disable SQLite for multi-worker
- [ ] Restrict `CORS_ORIGINS` to real frontends
- [ ] TLS termination (nginx / cloud LB) in front of uvicorn/gunicorn
- [ ] Run `alembic upgrade head` in deploy pipeline before traffic switch
- [ ] Configure `SENTRY_DSN` (or equivalent)
- [ ] Health check on `/api/health` for orchestrator
- [ ] Disk + automated backups with retention tested
- [ ] Rate limits tuned; consider Redis if scaling horizontally
- [ ] Do not expose `/docs` publicly (or protect behind VPN/auth)
- [ ] Resource limits (CPU/mem) on container / k8s
- [ ] Log aggregation (CloudWatch, ELK, Loki, …)

### Zero-downtime notes

1. Deploy new containers behind the load balancer **without** draining DB.
2. Prefer **expand/contract** migrations (add nullable columns → dual-write → backfill → drop old). Avoid destructive changes in the same release that serves old code.
3. Run `alembic upgrade head` as a **pre-rollout Job** (or entrypoint) before routing traffic to the new revision.
4. Keep at least 2 backend replicas; rolling update with readiness = `/api/health`.
5. SQLite is **not** suitable for multi-replica writes — switch to PostgreSQL first.

---

## Project layout

```
app_backend/
  main.py                 # FastAPI entry
  config.py               # Settings from env
  database.py             # Engine / session / Base
  models/                 # SQLAlchemy: user, signal, ml_model
  schemas/                # Pydantic request/response
  routes/                 # HTTP endpoints
  middleware/             # Auth, rate limit, JSON logging
  services/               # Business logic (metrics, signals)
  tests/                  # pytest: conftest + API tests
  migrations/             # Alembic
  docker/                 # Dockerfile + entrypoint
  docker-compose.yml
  .env.example
  requirements.txt
  README_BACKEND.md
```

---

## License / scope

Internal KONECTA Intelligence Hub component. Recognition/ML lives elsewhere (`vision_lab`, models); this package is API + storage only.
