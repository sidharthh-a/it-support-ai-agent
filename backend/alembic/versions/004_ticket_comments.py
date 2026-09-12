"""Add ticket_comments table

Revision ID: 004_ticket_comments
Revises: 003_auth_conversations
Create Date: 2026-09-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_ticket_comments'
down_revision: Union[str, None] = '003_auth_conversations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ticket_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ticket_comments_id'), 'ticket_comments', ['id'], unique=False)
    op.create_index(op.f('ix_ticket_comments_ticket_id'), 'ticket_comments', ['ticket_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ticket_comments_ticket_id'), table_name='ticket_comments')
    op.drop_index(op.f('ix_ticket_comments_id'), table_name='ticket_comments')
    op.drop_table('ticket_comments')
