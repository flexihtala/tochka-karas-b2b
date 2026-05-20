"""create tickets and processed_events tables

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
        'tickets',
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('seller_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('claimed_by', sa.Uuid(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('blocking_reason_id', sa.Uuid(), nullable=True),
        sa.Column('moderator_comment', sa.String(length=2000), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tickets_id'), 'tickets', ['id'], unique=False)
    op.create_index(op.f('ix_tickets_product_id'), 'tickets', ['product_id'], unique=False)
    op.create_index(op.f('ix_tickets_seller_id'), 'tickets', ['seller_id'], unique=False)
    op.create_index(op.f('ix_tickets_status'), 'tickets', ['status'], unique=False)
    op.create_index(op.f('ix_tickets_claimed_by'), 'tickets', ['claimed_by'], unique=False)

    op.create_table(
        'processed_events',
        sa.Column('sender_service', sa.String(length=32), nullable=False),
        sa.Column('idempotency_key', sa.Uuid(), nullable=False),
        sa.Column(
            'response_cached',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sender_service', 'idempotency_key', name='uq_processed_events_sender_key'),
    )
    op.create_index(op.f('ix_processed_events_id'), 'processed_events', ['id'], unique=False)
    op.create_index(op.f('ix_processed_events_sender_service'), 'processed_events', ['sender_service'], unique=False)
    op.create_index(
        op.f('ix_processed_events_idempotency_key'),
        'processed_events',
        ['idempotency_key'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_processed_events_idempotency_key'), table_name='processed_events')
    op.drop_index(op.f('ix_processed_events_sender_service'), table_name='processed_events')
    op.drop_index(op.f('ix_processed_events_id'), table_name='processed_events')
    op.drop_table('processed_events')

    op.drop_index(op.f('ix_tickets_claimed_by'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_status'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_seller_id'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_product_id'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_id'), table_name='tickets')
    op.drop_table('tickets')
