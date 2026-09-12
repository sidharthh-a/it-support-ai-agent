"""Initial schema migration with pgvector

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import pgvector

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='user'),
        sa.Column('department', sa.String(length=100), nullable=False, server_default='General'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    # 2. devices
    op.create_table(
        'devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('device_name', sa.String(length=255), nullable=False),
        sa.Column('serial_number', sa.String(length=100), nullable=False),
        sa.Column('os', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_devices_id'), 'devices', ['id'], unique=False)
    op.create_index(op.f('ix_devices_serial_number'), 'devices', ['serial_number'], unique=True)

    # 3. support_tickets
    op.create_table(
        'support_tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_number', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='open'),
        sa.Column('priority', sa.String(length=50), nullable=False, server_default='medium'),
        sa.Column('category', sa.String(length=100), nullable=False, server_default='software'),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('assigned_to_id', sa.Integer(), nullable=True),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_support_tickets_category'), 'support_tickets', ['category'], unique=False)
    op.create_index(op.f('ix_support_tickets_id'), 'support_tickets', ['id'], unique=False)
    op.create_index(op.f('ix_support_tickets_priority'), 'support_tickets', ['priority'], unique=False)
    op.create_index(op.f('ix_support_tickets_status'), 'support_tickets', ['status'], unique=False)
    op.create_index(op.f('ix_support_tickets_ticket_number'), 'support_tickets', ['ticket_number'], unique=True)

    # 4. incidents
    op.create_table(
        'incidents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False, server_default='P3'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='investigating'),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('affected_service', sa.String(length=100), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incidents_id'), 'incidents', ['id'], unique=False)
    op.create_index(op.f('ix_incidents_severity'), 'incidents', ['severity'], unique=False)
    op.create_index(op.f('ix_incidents_status'), 'incidents', ['status'], unique=False)

    # 5. error_logs
    op.create_table(
        'error_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('service_name', sa.String(length=100), nullable=False),
        sa.Column('error_code', sa.String(length=100), nullable=False),
        sa.Column('log_message', sa.Text(), nullable=False),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_error_logs_error_code'), 'error_logs', ['error_code'], unique=False)
    op.create_index(op.f('ix_error_logs_id'), 'error_logs', ['id'], unique=False)
    op.create_index(op.f('ix_error_logs_service_name'), 'error_logs', ['service_name'], unique=False)
    op.create_index(op.f('ix_error_logs_timestamp'), 'error_logs', ['timestamp'], unique=False)

    # 6. resolutions
    op.create_table(
        'resolutions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('solution_summary', sa.Text(), nullable=False),
        sa.Column('steps_taken', sa.Text(), nullable=False),
        sa.Column('resolved_by_id', sa.Integer(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticket_id')
    )
    op.create_index(op.f('ix_resolutions_id'), 'resolutions', ['id'], unique=False)

    # 7. ticket_history
    op.create_table(
        'ticket_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('changed_by_id', sa.Integer(), nullable=True),
        sa.Column('field_changed', sa.String(length=100), nullable=False),
        sa.Column('old_value', sa.String(length=255), nullable=True),
        sa.Column('new_value', sa.String(length=255), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ticket_history_id'), 'ticket_history', ['id'], unique=False)

    # 8. knowledge_documents
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False, server_default='markdown'),
        sa.Column('source_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_documents_category'), 'knowledge_documents', ['category'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_id'), 'knowledge_documents', ['id'], unique=False)

    # 9. document_chunks
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=1536), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['knowledge_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_chunks_id'), 'document_chunks', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_document_chunks_id'), table_name='document_chunks')
    op.drop_table('document_chunks')
    op.drop_index(op.f('ix_knowledge_documents_id'), table_name='knowledge_documents')
    op.drop_index(op.f('ix_knowledge_documents_category'), table_name='knowledge_documents')
    op.drop_table('knowledge_documents')
    op.drop_index(op.f('ix_ticket_history_id'), table_name='ticket_history')
    op.drop_table('ticket_history')
    op.drop_index(op.f('ix_resolutions_id'), table_name='resolutions')
    op.drop_table('resolutions')
    op.drop_index(op.f('ix_error_logs_timestamp'), table_name='error_logs')
    op.drop_index(op.f('ix_error_logs_service_name'), table_name='error_logs')
    op.drop_index(op.f('ix_error_logs_id'), table_name='error_logs')
    op.drop_index(op.f('ix_error_logs_error_code'), table_name='error_logs')
    op.drop_table('error_logs')
    op.drop_index(op.f('ix_incidents_status'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_severity'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_id'), table_name='incidents')
    op.drop_table('incidents')
    op.drop_index(op.f('ix_support_tickets_ticket_number'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_status'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_priority'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_id'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_category'), table_name='support_tickets')
    op.drop_table('support_tickets')
    op.drop_index(op.f('ix_devices_serial_number'), table_name='devices')
    op.drop_index(op.f('ix_devices_id'), table_name='devices')
    op.drop_table('devices')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
