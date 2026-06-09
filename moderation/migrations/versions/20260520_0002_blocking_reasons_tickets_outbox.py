"""create blocking_reasons, tickets, outbox tables

Revision ID: 20260520_0002
Revises: 20260520_0001
Create Date: 2026-05-20
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260520_0002'
down_revision: str | None = '20260520_0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'blocking_reasons',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('hard_block', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_blocking_reasons_id'), 'blocking_reasons', ['id'], unique=False)
    op.create_index(op.f('ix_blocking_reasons_code'), 'blocking_reasons', ['code'], unique=True)

    op.create_table(
        'tickets',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('seller_id', sa.Uuid(), nullable=False),
        sa.Column('category_id', sa.Uuid(), nullable=True),
        sa.Column('kind', sa.String(length=8), server_default='CREATE', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('queue_priority', sa.Integer(), server_default='3', nullable=False),
        sa.Column('claimed_by', sa.Uuid(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('claim_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('blocking_reason_id', sa.Uuid(), nullable=True),
        sa.Column('moderator_comment', sa.Text(), nullable=True),
        sa.Column('json_before', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('json_after', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('queue_priority BETWEEN 1 AND 4', name='ck_tickets_queue_priority_range'),
        sa.ForeignKeyConstraint(['claimed_by'], ['moderators.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['blocking_reason_id'], ['blocking_reasons.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tickets_id'), 'tickets', ['id'], unique=False)
    op.create_index(op.f('ix_tickets_product_id'), 'tickets', ['product_id'], unique=True)
    op.create_index(op.f('ix_tickets_seller_id'), 'tickets', ['seller_id'], unique=False)
    op.create_index(op.f('ix_tickets_category_id'), 'tickets', ['category_id'], unique=False)
    op.create_index(op.f('ix_tickets_status'), 'tickets', ['status'], unique=False)
    op.create_index(op.f('ix_tickets_claimed_by'), 'tickets', ['claimed_by'], unique=False)
    # Композитный индекс для запроса claim_next (status + queue_priority + created_at).
    op.create_index(
        'ix_tickets_status_priority_created',
        'tickets',
        ['status', 'queue_priority', 'created_at'],
        unique=False,
    )

    op.create_table(
        'outbox',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('idempotency_key', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('target_service', sa.String(length=32), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=16), server_default='PENDING', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(length=2048), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_outbox_id'), 'outbox', ['id'], unique=False)
    op.create_index(op.f('ix_outbox_idempotency_key'), 'outbox', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_outbox_target_service'), 'outbox', ['target_service'], unique=False)
    op.create_index(op.f('ix_outbox_status'), 'outbox', ['status'], unique=False)
    op.create_index(op.f('ix_outbox_next_retry_at'), 'outbox', ['next_retry_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_outbox_next_retry_at'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_status'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_target_service'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_idempotency_key'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_id'), table_name='outbox')
    op.drop_table('outbox')

    op.drop_index('ix_tickets_status_priority_created', table_name='tickets')
    op.drop_index(op.f('ix_tickets_claimed_by'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_status'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_category_id'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_seller_id'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_product_id'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_id'), table_name='tickets')
    op.drop_table('tickets')

    op.drop_index(op.f('ix_blocking_reasons_code'), table_name='blocking_reasons')
    op.drop_index(op.f('ix_blocking_reasons_id'), table_name='blocking_reasons')
    op.drop_table('blocking_reasons')
