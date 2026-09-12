# Database Schema

PostgreSQL 16 + pgvector. All schema changes via Alembic migrations.

## Migrations

| Migration | Contents |
| :--- | :--- |
| `001_initial_migration` | users, devices, support_tickets, incidents, error_logs, resolutions, ticket_history, knowledge_documents, document_chunks (vector column) |
| `002_update_vector_dimension` | Align vector column with `EMBEDDING_DIMENSION` |
| `003_auth_conversations` | User auth columns (`hashed_password`, role normalization to admin/support/employee, active, timestamps), `conversations`, `chat_messages` |
| `004_ticket_comments` | `ticket_comments` table |

## Entity-Relationship Diagram

```
                       ┌──────────────┐
                       │    users     │
                       │──────────────│
                       │ id PK        │
                       │ email UQ     │
                       │ hashed_password
                       │ role         │  admin | support | employee
                       │ is_active    │
                       └──┬───────┬───┘
              creates/owns│       │assigned_to
        ┌─────────────────┘       └──────────────┐
        ▼                                        ▼
┌──────────────────┐   device_id   ┌────────────────────┐
│ support_tickets  │◄──────────────│      devices       │
│──────────────────│               └────────────────────┘
│ ticket_number UQ │
│ status, priority │
│ category         │
└──┬───────┬───────┘
   │ 1:n    │ 1:n
   ▼        ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ ticket_comments  │      │   ticket_history │      │   resolutions    │
│ (author, body,   │      │ (audit trail:    │      │ (solution, steps,│
│  created_at)     │      │  field changes)  │      │  resolved_at)    │
└──────────────────┘      └──────────────────┘      └──────────────────┘

┌──────────────────┐  ticket_id   ┌──────────────────┐
│    incidents     │─────────────►│ support_tickets  │
│ severity/status  │              └──────────────────┘
└──────────────────┘

┌──────────────────┐  device_id, ticket_id
│    error_logs    │──────► devices / support_tickets
│ service_name     │
│ error_code       │
│ stack_trace      │
└──────────────────┘

┌──────────────────┐         ┌──────────────────┐
│  conversations   │ 1:n ──► │   chat_messages   │
│ user_id FK       │         │ role, content     │
│ title, updated_at│         │ tools_used JSONB  │
└──────────────────┘         │ rag_sources JSONB │
                             │ sql_sources JSONB │
                             │ ticket_created/   │
                             │  _updated JSONB   │
                             └──────────────────┘

┌──────────────────────┐  1:n  ┌──────────────────────┐
│ knowledge_documents  │─────► │   document_chunks    │
│ title, category      │       │ chunk_index          │
│ embedding_status     │       │ embedding vector(N)  │
│ chunk_count          │       │ content text         │
└──────────────────────┘       └──────────────────────┘
```

## Design Notes

- **Roles**: canonical values `admin` / `support` / `employee`; legacy values (`user`, `technician`) are normalized on read for backward compatibility.
- **JSONB metadata columns** (`tools_used`, `rag_sources`, `sql_sources`, `ticket_created`, `ticket_updated`) let messages replay the full grounded-agent trace without schema churn.
- **pgvector**: `document_chunks.embedding` is a `vector(N)` column matching `EMBEDDING_DIMENSION`; similarity search uses cosine distance.
- **Indexes** exist on all foreign keys, ticket `status`/`priority`/`category`, and conversation `(user_id, updated_at)` for list queries.
- **Timestamps** are timezone-aware UTC (`DateTime(timezone=True)`).
