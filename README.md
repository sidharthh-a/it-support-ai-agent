# IT Support AI Agent Platform

An enterprise-grade, production-style **AI IT Support platform** with a grounded **Agentic RAG + SQL** architecture (LangGraph-style tool loop), **FastAPI**, **SQLAlchemy 2.x**, **PostgreSQL (pgvector)**, **Alembic**, JWT authentication with RBAC, and a modern **React + TypeScript + Vite + Tailwind** dashboard with **streaming chat (SSE)**.

> **Grounding guarantee:** Gemini is only a *synthesizer* behind deterministic retrieval. The database is the single source of truth; every troubleshooting claim is backed by retrieved documents, SQL evidence, or logged incidents. With no LLM key configured, the system runs in fully deterministic fallback mode.

---

## ✨ Feature Highlights

| Area | Capabilities |
| :--- | :--- |
| **AI Assistant** | Streaming SSE responses, tool-execution badges, RAG/SQL citation cards, error-log evidence, typing animation, cancel/retry/regenerate, markdown + code highlighting |
| **Conversations** | Persistent history (create/rename/delete/search/resume), messages preserve role, timestamp, tool usage, citations and ticket references |
| **Tickets** | Full CRUD, assign, escalate, comment threads, timeline, related error logs, related RAG documents, status/priority/category/assignee filters |
| **Knowledge Base** | Upload PDF/TXT/MD/JSON, chunk counts + embedding status, reindex, preview, semantic search, retrieved-chunk highlighting |
| **Analytics** | Pure SQL aggregation dashboards (Recharts): tickets by priority, resolution rate, incidents by category, top recurring errors, daily trend, knowledge coverage, avg resolution time |
| **Auth** | JWT (bcrypt password hashing), roles: **admin / support / employee**, role-protected endpoints |
| **Admin** | User management, system health, embedding/gemini model info, vector dimension, bulk reindex, DB health |
| **Hardening** | Security headers, per-IP rate limiting, request IDs, structured logging, strict environment validation, no wildcard CORS in production, `/health` `/ready` `/live` probes |

**6 Agentic Tools** (deterministic, repository-backed):
`search_documents` · `search_tickets` · `get_ticket_history` · `search_error_logs` · `create_ticket` · `update_ticket`

---

## 🏗 Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        nginx (reverse proxy)                          │
│        serves React SPA   •   proxies /api → backend (SSE-safe)       │
└──────────────────────────────────┬───────────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          FastAPI backend                              │
│  Middleware: RequestID → SecurityHeaders → RateLimit → CORS           │
│  Routers: auth · chat · conversations · tickets · incidents ·         │
│           knowledge · devices · analytics · admin · health            │
└───────────────┬──────────────────────────────────┬───────────────────┘
                ▼                                  ▼
┌──────────────────────────┐        ┌──────────────────────────────┐
│   Grounded Agent Graph   │        │  Repositories / Services     │
│  1. Intent Router (LLM/  │        │  (SOLID, dependency-injected)│
│     deterministic rules) │        └──────────────┬───────────────┘
│  2. Tool Loop (6 tools)  │                       │
│  3. Grounded Synthesis   │                       │
│     (Gemini, citations   │                       │
│      enforced; rule-     │                       │
│      based fallback)     │                       │
└───────────────┬──────────┘                       │
                │  RAG: pgvector similarity        │
                │  SQL: repository queries         │
                ▼                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL + pgvector (source of truth)            │
│  users · devices · support_tickets · ticket_comments · incidents ·    │
│  error_logs · resolutions · ticket_history · conversations ·          │
│  messages · knowledge_documents · document_chunks (vector)            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Folder Structure

```
IT Support AI Agent/
├── backend/
│   ├── app/
│   │   ├── agents/        # intent router, agent graph, grounded synthesis, SSE streaming
│   │   ├── api/v1/        # routers: auth, chat, conversations, tickets, knowledge, ...
│   │   ├── core/          # config, security (JWT/bcrypt), deps, middleware, logging
│   │   ├── db/            # session, base
│   │   ├── models/        # SQLAlchemy 2.x models
│   │   ├── rag/           # embeddings, chunker, pgvector service
│   │   ├── repositories/  # repository pattern (all DB access)
│   │   ├── schemas/       # Pydantic request/response models
│   │   ├── services/      # analytics_service (SQL aggregations)
│   │   └── tools/         # deterministic agent tools
│   ├── alembic/versions/  # 001 initial · 002 vector dim · 003 auth+conversations · 004 comments
│   ├── tests/             # 226 tests (auth, SSE, grounding, CRUD, analytics, admin, middleware)
│   ├── seed.py            # synthetic IT dataset (users, devices, tickets, logs, RAG docs)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/    # chat (evidence cards, bubbles, conversations panel), layout, ui
│   │   ├── context/       # AuthContext, ThemeContext
│   │   ├── pages/         # Login, Chat, Tickets, Knowledge, Analytics, Settings
│   │   ├── services/      # api.ts (JWT client), stream.ts (SSE)
│   │   └── types/
│   ├── nginx.conf         # production reverse proxy (SSE-safe)
│   ├── Dockerfile         # multi-stage build → nginx
│   └── tailwind.config.js
├── docs/                  # architecture.md, api.md, database.md, deployment.md
├── docker-compose.yml     # postgres + backend + nginx (+ dev profile for Vite)
├── .env.example
└── README.md
```

---

## 🚀 Quick Start (Docker Compose)

```bash
# 1. Configure environment
cp .env.example .env
# → set SECRET_KEY (openssl rand -hex 32); optionally add GEMINI_API_KEY

# 2. Build & launch the full stack (postgres + backend + nginx/SPA)
docker compose up --build -d

# 3. Open (host port configurable via NGINX_PORT, default 3001)
#   Frontend:   http://localhost:3001
#   API docs:   http://localhost:8000/docs  (direct) or via the proxy: /api/docs
#   Health:     http://localhost:3001/api/v1/health
#
# Sign in with the seeded demo admin: admin@acme-corp.com / Demo1234!
# (the seed script provisions this account when it provisions sample data;
#  the first self-registered user also becomes admin when no admin exists)

# Development profile: Vite dev server with hot reload on :5173
docker compose --profile dev up frontend-dev
```

---

## 💻 Local Development

### Backend

```bash
cd backend
python -m venv venv && venv\Scripts\activate   # Windows; source venv/bin/activate on Unix
pip install -r requirements.txt

alembic upgrade head      # schema (incl. pgvector extension)
python seed.py            # synthetic IT dataset + sample RAG documents
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev               # http://localhost:5173
```

### Environment

All variables are documented in [`.env.example`](.env.example): database, Gemini key/model, embedding provider (local 384-dim MiniLM by default / OpenAI 1536-dim), JWT `SECRET_KEY`, CORS allow-list, rate limit. Production mode *rejects* default secrets and wildcard CORS at startup.

---

## 🧪 Testing

```bash
cd backend
python -m pytest -v        # 226 tests, all Gemini calls mocked
```

Coverage includes: authentication & role permissions, SSE streaming contract, conversation history, knowledge CRUD + reindex, ticket CRUD + comments, analytics SQL aggregations, admin endpoints, grounding safety cases, middleware (request IDs, security headers, rate limiting), config validation.

Frontend typecheck + production build:

```bash
cd frontend
npx tsc --noEmit && npm run build
```

---

## 🔌 API Summary

Full reference: [`docs/api.md`](docs/api.md) · Interactive: `/docs` (Swagger UI)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register user (first user becomes admin) |
| `POST` | `/api/v1/auth/login` | Obtain JWT access token |
| `GET` | `/api/v1/auth/me` | Current user profile |
| `POST` | `/api/v1/chat` | Grounded agent answer (non-streaming) |
| `POST` | `/api/v1/chat/stream` | **SSE** stream: tokens + tool + citation events (JSON body) |
| `GET/POST/PATCH/DELETE` | `/api/v1/conversations` | Persistent conversation history |
| `GET/POST` | `/api/v1/tickets` | List/filter / create tickets |
| `PATCH` | `/api/v1/tickets/{id}` | Update status/priority/assignee |
| `POST` | `/api/v1/tickets/{id}/comments` | Comment thread |
| `GET` | `/api/v1/tickets/{id}/logs` | Related error logs |
| `GET` | `/api/v1/knowledge` / `POST` upload | List, upload (PDF/TXT/MD/JSON) |
| `POST` | `/api/v1/knowledge/{id}/reindex` | Re-embed a document |
| `GET` | `/api/v1/analytics/dashboard` | SQL-aggregated dashboard metrics |
| `GET` | `/api/v1/admin/system` | Model, embedding & DB health (admin) |
| `GET` | `/api/v1/health` `/ready` `/live` | Liveness / readiness probes |

---

## 🔒 Security & Data Integrity

- **JWT + bcrypt**: passwords hashed with bcrypt; tokens signed HS256 with configurable expiry.
- **RBAC**: `admin` (users/knowledge/analytics), `support` (tickets), `employee` (chat + own tickets) enforced in dependencies and routers.
- **No SQL injection**: LLMs never emit raw SQL — all access goes through typed repositories.
- **Grounding validator**: rejects fabricated procedures/steps not present in retrieved evidence; deterministic safety overrides run before the LLM.
- **Production hardening**: security headers, per-IP rate limiting, request IDs on every response, explicit CORS allow-list, environment validation.
- **Synthetic data only**: seed data is realistic, non-PII.

---

## 📚 Documentation

- [`docs/architecture.md`](docs/architecture.md) — system & agent design, RAG pipeline, intent routing
- [`docs/api.md`](docs/api.md) — complete endpoint reference
- [`docs/database.md`](docs/database.md) — schema, ER diagram, migrations
- [`docs/deployment.md`](docs/deployment.md) — Docker, nginx, profiles, production checklist
