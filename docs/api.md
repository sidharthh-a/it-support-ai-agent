# API Reference

Base URL: `/api/v1` · Auth: `Authorization: Bearer <JWT>` · Interactive docs: `/docs`

Role values: `admin` · `support` · `employee`. Endpoints marked **guarded** reject requests without a valid JWT carrying an allowed role.

## Authentication — `/auth`

| Method | Path | Auth | Description |
| :--- | :--- | :--- | :--- |
| POST | `/auth/register` | public | Register. Response 201. If no admin exists yet, the first registered user is promoted to `admin` (bootstrap). |
| POST | `/auth/login` | public | JSON body `{ "email", "password" }` → `{ access_token, token_type, expires_in, user }` |
| GET | `/auth/me` | JWT | Current user profile |
| POST | `/auth/change-password` | JWT | `{ current_password, new_password }` → updated user |
| GET | `/auth/users` | **admin** | List users |
| POST | `/auth/users` | **admin** | Create user with any role |
| PATCH | `/auth/users/{user_id}` | **admin** | Update user (role, name, department, active, password) |

There is no OAuth2 form-login route; Swagger "Authorize" accepts the bearer token directly (obtain it via `POST /auth/login`).

## Chat — `/chat`

| Method | Path | Auth | Description |
| :--- | :--- | :--- | :--- |
| POST | `/chat` | optional JWT | Grounded, non-streaming answer. Body: `{ message, conversation_id?, conversation_history? }`. Response: `{ answer, tools_used, ticket_created?, ticket_updated?, rag_sources?, sql_sources? }` |
| POST | `/chat/stream` | optional JWT | **SSE** (JSON body, same fields as `/chat`). Events: `start`, `tool`, `token`, `meta`, `done`, `error`. Personalizes ownership when a JWT is present; persists messages into `conversation_id` if provided. |

Agent tools (deterministic, repository-backed): `search_documents`, `search_tickets`, `get_ticket_history`, `search_error_logs`, `create_ticket`, `update_ticket`.

## Conversations — `/conversations`

| Method | Path | Auth | Description |
| :--- | :--- | :--- | :--- |
| GET | `/conversations` | optional JWT | List conversations (per-user when JWT present). Query: `search` filters by title/preview |
| POST | `/conversations` | optional JWT | Create conversation `{ title? }` |
| GET | `/conversations/search` | — | Required query `q` → matching conversations |
| GET | `/conversations/{id}` | — | Conversation + full message history |
| PATCH | `/conversations/{id}` | — | Rename `{ title }` |
| DELETE | `/conversations/{id}` | — | Delete conversation + messages |
| GET | `/conversations/{id}/messages` | — | Message list only |

Messages preserve `role`, `content`, `tools_used`, `rag_sources`, `sql_sources`, `ticket_created` / `ticket_updated`, `grounded`, `confidence`, `evidence_used`, `created_at` (table: `chat_messages`).

## Tickets — `/tickets` *(currently unauthenticated — see note)*

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/tickets` | Filters: `query`, `status`, `priority`, `category`, `assigned_to_id` |
| POST | `/tickets` | Create `{ title, description, priority, category, device_id? }` |
| GET | `/tickets/{id}` | Detail incl. creator, assignee, resolution, history, comments |
| PATCH | `/tickets/{id}` | Update status/priority/assignee/category/title/description |
| POST | `/tickets/{id}/escalate` | Escalate |
| GET | `/tickets/{id}/history` | Audit trail |
| GET | `/tickets/{id}/comments` | Comment thread |
| POST | `/tickets/{id}/comments` | Add comment `{ body }` |
| GET | `/tickets/{id}/logs` | Related error logs |

Statuses: `open` · `in_progress` · `resolved` · `closed` · `escalated` · Priorities: `low` · `medium` · `high` · `critical`

> **Security note:** the tickets, analytics, devices, incidents, and knowledge-read routers currently have **no auth dependency** (their test suites call them anonymously). Role guards exist on all `/auth/users*` and `/admin/*` routes, and on knowledge delete/reindex. Adding guards to tickets/analytics is a tracked follow-up.

## Knowledge Base — `/knowledge`

| Method | Path | Auth | Description |
| :--- | :--- | :--- | :--- |
| GET | `/knowledge` | open | List documents with chunk counts |
| GET | `/knowledge/search` | open | pgvector semantic search: `q`, `limit` |
| GET | `/knowledge/{id}/preview` | open | Concatenated content preview `{ content, truncated }` |
| GET | `/knowledge/{id}/chunks/{chunk_id}` | open | Single chunk |
| POST | `/knowledge` | open | Upload raw JSON `{ title, category, content, file_type?, source_url? }` → 201 |
| POST | `/knowledge/upload` | open | Multipart file upload (PDF/TXT/MD/JSON): `title`, `category`, `file`, `source_url?` → 201 |
| POST | `/knowledge/{id}/reindex` | **support/admin** | Re-chunk + re-embed |
| DELETE | `/knowledge/{id}` | **support/admin** | Delete document + chunks (204) |

## Analytics *(currently unauthenticated)*

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/analytics` | Summary counts + AI self-service resolution rate |
| GET | `/analytics/dashboard` | SQL aggregations: `days` (7–90, default 30) → priority/category breakdowns, daily trend, avg resolution hours, top recurring errors, knowledge coverage, per-category resolution rates |

## Admin — all routes **admin only**

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/admin/system` | Environment, version, Python/platform, DB health+latency, embedding provider/model/dimension/coverage, Gemini model+configured flag |
| POST | `/admin/reindex-all` | Re-embed all documents → `{ reindexed, skipped, dimension }` |
| GET | `/admin/users` | List users |
| POST | `/admin/users` | Create user |
| PATCH | `/admin/users/{id}` | Update user |
| GET | `/admin/logs` | Recent system logs (from `error_logs`) |

## Devices & Incidents *(currently unauthenticated)*

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/devices` | `query` search across name/serial/user |
| GET | `/devices/{id}` | Device detail |
| POST | `/devices` | Create device |
| GET | `/incidents` | List incidents |
| GET | `/incidents/{id}` | Incident detail |
| POST | `/incidents` | Create incident |
| PATCH | `/incidents/{id}` | Update incident |

## Health & Ops

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/health` | Full detail: DB status, embedding info, LLM config, environment, version |
| GET | `/ready` | Readiness (DB reachable) |
| GET | `/live` | Liveness (process up) |

Every response carries `X-Request-ID`. Rate limiting: `RATE_LIMIT_PER_MINUTE` per client IP; `/api/v1/health`, `/ready`, `/live`, docs and `/` are exempt.
