# Architecture

## System Overview

```
Browser ──► nginx ──► FastAPI ──► Agent Graph ──► Tools ──► PostgreSQL/pgvector
                          │             │
                          │             ├── Intent Router (Gemini structured output)
                          │             ├── 6 Deterministic Tools (repositories)
                          │             └── Response Generator (grounded synthesis)
                          └── SSE: token deltas + tool/citation events
```

## Layers

| Layer | Location | Responsibility |
| :--- | :--- | :--- |
| Presentation | `frontend/` | React 19 + Vite + Tailwind SPA; SSE client; Recharts dashboards |
| API | `backend/app/api/v1/` | Thin FastAPI routers: validation, auth, orchestration |
| Security | `backend/app/core/` | JWT auth (`security.py`), DI dependencies (`deps.py`), middleware, logging, config validation. `BACKEND_CORS_ORIGINS` accepts both comma-separated and JSON forms from env vars/.env via the `NoDecode` annotation (regression-tested in `tests/test_config.py`) |
| Agents | `backend/app/agents/` | Intent router → tool loop → grounded response generator; SSE stream wrapper |
| Tools | `backend/app/tools/` | 6 deterministic tools wrapping repositories |
| Repositories | `backend/app/repositories/` | All SQL access (repository pattern, injectable) |
| Services | `backend/app/services/` | Analytics aggregations (pure SQL) |
| Data | `backend/app/models/`, `alembic/` | SQLAlchemy 2.x models + migrations |

## Agent Pipeline (grounded by construction)

1. **Deterministic overrides first.** Before any LLM call, rule-based handlers answer known intents (greetings, follow-ups) with zero hallucination risk.
2. **Intent routing.** Gemini structured output classifies the query (`KNOWLEDGE` / `TICKET` / `LOG` / `CASUAL` / `AMBIGUOUS`); a deterministic fallback classifier runs when no key is configured.
3. **Tool loop.** The agent invokes only repository-backed tools — vector search (`search_documents`), SQL lookups (`search_tickets`, `get_ticket_history`, `search_error_logs`), and guarded mutations (`create_ticket`, `update_ticket`).
4. **Grounded synthesis.** The response generator prompts Gemini *only with retrieved evidence* and validates the output:
   - step-by-step instructions must correspond to evidence content (inline or newline numbered steps are normalized before checking),
   - text-fallback documents (score 0.0) must pass a lexical-relevance gate,
   - no-match queries get a safe "no grounded procedure found" response.
5. **Streaming.** The `POST /chat/stream` SSE endpoint replays tool/citation events, then streams the final grounded answer token-by-token. Metadata (citations, tickets created, tool traces) is emitted as structured `meta` events, so grounding is preserved in the stream.

## Frontend Architecture

- **Context providers**: `AuthContext` (JWT + role helpers), `ThemeContext` (dark/light, persisted).
- **Services**: `api.ts` (typed fetch client, automatic Bearer header), `stream.ts` (SSE reader with cancel via `AbortController`).
- **Routing**: `react-router-dom` with protected routes by role.
- **Ports**: Vite dev server on :5173 proxies `/api` to a backend on `localhost:8000` (which expects the compose Postgres published on loopback `127.0.0.1:5432`); the production nginx stack serves the SPA on `${NGINX_PORT:-3001}`.
- **Design system**: Tailwind theme tokens (dark/light), Lucide icons, Framer Motion transitions, React Markdown + syntax highlighting for chat.

## Key Invariants

- The database is the source of truth; the LLM never invents data.
- Analytics come from SQL aggregations, never hardcoded.
- All mutations go through repositories with Pydantic-validated inputs.
- Tests mock every Gemini call — CI runs with zero network access.
