# Deployment

## Production Stack (docker-compose)

```
            ┌────────────────────────────────────────────┐
 :${NGINX_PORT:-3001} ──►│                nginx (SPA)                 │
            │  static React build  •  /api → backend     │
            │  SSE-safe proxying (no buffering)          │
            └───────────────────┬────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  backend (FastAPI)    │
                    │  alembic upgrade head │
                    │  seed.py (idempotent) │
                    │  uvicorn :8000        │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  db (pgvector/pg16)   │
                    │  volume: pgdata       │
                    └───────────────────────┘
```

Services: `db` (healthchecked) → `backend` (runs migrations + idempotent seed, then serves) → `nginx` (serves the built SPA from the multi-stage `frontend/Dockerfile` and reverse-proxies `/api`, with `proxy_buffering off` so SSE token deltas stream in real time).

### Bring-up

```bash
cp .env.example .env          # set SECRET_KEY; optionally GEMINI_API_KEY
docker compose up --build -d
docker compose ps             # all healthy?
curl http://localhost:3001/api/v1/health   # through nginx (backend :8000 is container-internal only)
# SPA (host port = NGINX_PORT, default 3001):  http://localhost:3001
# Swagger:                                     http://localhost:8000/docs (dev) — not exposed by the compose nginx
# Demo admin login: admin@acme-corp.com / Demo1234!
```

### Development profile

```bash
# Vite dev server with hot reload on :5173 (mounted source, API → backend:8000)
docker compose --profile dev up frontend-dev
```

Local (non-Docker) development: see README — `uvicorn app.main:app --reload` + `npm run dev`.

## Environment Profiles

| Variable | development | production |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | `production` |
| `SECRET_KEY` | default allowed | **required, non-default** (validated at startup) |
| `BACKEND_CORS_ORIGINS` | localhost defaults | explicit allow-list; wildcard `*` is rejected at startup. Accepts BOTH comma-separated and JSON forms |
| `NGINX_PORT` | `3001` host port for the SPA (raise if :3000 is taken) | same |
| `EMBEDDING_DIMENSION` | `384` (MiniLM) | must match your provider (`1536` for OpenAI) + reindex |
| `RATE_LIMIT_PER_MINUTE` | `120` | tune per traffic; health probes are exempt |

## Health Probes & Observability

- `GET /api/v1/live` — liveness (process up)
- `GET /api/v1/ready` — readiness (DB reachable)
- `GET /api/v1/health` — full detail (DB status, embedding provider/dimension, LLM config, environment, version); per-field system detail (latency, embedding coverage) is on admin-only `GET /api/v1/admin/system`
- Every response carries `X-Request-ID`; unhandled exceptions are logged with it and returned as a safe 500.

## Production Checklist

- [x] Migrations run automatically before serving (`alembic upgrade head`)
- [x] Non-root defaults, pinned base images, `.dockerignore` on all build contexts
- [x] Backend image installs CPU-only torch first + BuildKit pip cache mount (avoids multi-GB CUDA wheels; fast rebuilds)
- [x] Secrets only via env; `SECRET_KEY` enforced non-default in production
- [x] CORS allow-list (no wildcard), security headers on both nginx and FastAPI
- [x] Rate limiting + request IDs enabled
- [x] Health endpoints for orchestrator probes; container healthchecks wired in compose
- [x] Seed script idempotent (skips when data exists)
- [x] Model cache persisted via named volume (`backend_models`) to avoid re-downloading embeddings
- [x] Verified end-to-end: db/backend healthy, nginx serving, login + authenticated API calls working
- [ ] TLS termination (add certs / upstream LB in front of nginx)
- [ ] External secret manager for `SECRET_KEY` / `GEMINI_API_KEY` in real deployments
- [ ] Log shipping / APM integration of your choice
- [ ] Auth guards on tickets/analytics/devices/incidents routers (currently open; tracked follow-up)
