"""Add users.hashed_password, users.is_active, conversations and chat_messages

Revision ID: 003_auth_conversations
Revises: 002_vector_dim_384
Create Date: 2026-09-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_auth_conversations'
down_revision: Union[str, None] = '002_vector_dim_384'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Auth columns on users ---
    op.add_column('users', sa.Column('hashed_password', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))

    # --- Conversations ---
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False, server_default='New conversation'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversations_id'), 'conversations', ['id'], unique=False)
    op.create_index(op.f('ix_conversations_user_id'), 'conversations', ['user_id'], unique=False)
    op.create_index(op.f('ix_conversations_updated_at'), 'conversations', ['updated_at'], unique=False)

    # --- Messages ---
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tools_used', sa.JSON(), nullable=True),
        sa.Column('rag_sources', sa.JSON(), nullable=True),
        sa.Column('sql_sources', sa.JSON(), nullable=True),
        sa.Column('ticket_created', sa.JSON(), nullable=True),
        sa.Column('ticket_updated', sa.JSON(), nullable=True),
        sa.Column('grounded', sa.Boolean(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('evidence_used', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_id'), 'chat_messages', ['id'], unique=False)
    op.create_index(op.f('ix_chat_messages_conversation_id'), 'chat_messages', ['conversation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_messages_conversation_id'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index(op.f('ix_conversations_updated_at'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_user_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_id'), table_name='conversations')
    op.drop_table('conversations')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'hashed_password')
