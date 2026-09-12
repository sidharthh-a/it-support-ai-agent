"""Update embedding vector dimension from 1536 to 384

Changes document_chunks.embedding column from Vector(1536) to Vector(384)
to match the local SentenceTransformers model all-MiniLM-L6-v2.

Old data (1536-dim OpenAI embeddings) is incompatible and must be cleared.
Re-ingestion via seed.py or run_live_integration.py is required after this migration.

Revision ID: 002_vector_dim_384
Revises: 001_initial_schema
Create Date: 2026-08-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import pgvector
import pgvector.sqlalchemy

revision: str = '002_vector_dim_384'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension exists (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Drop old 1536-dim column and recreate as 384-dim
    # (ALTER COLUMN type is not supported directly for vector; drop + add is required)
    op.drop_column('document_chunks', 'embedding')
    op.add_column(
        'document_chunks',
        sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=384), nullable=True)
    )

    # Create HNSW index on the new 384-dim column for fast cosine similarity search
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    # Remove HNSW index
    op.execute(
        "DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;"
    )
    # Revert to 1536-dim column
    op.drop_column('document_chunks', 'embedding')
    op.add_column(
        'document_chunks',
        sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=1536), nullable=True)
    )
