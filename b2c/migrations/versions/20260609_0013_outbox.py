"""create outbox table for b2c (US-ORD-03 — async retry / fulfill)

Revision ID: 20260609_0013
Revises: 20260609_0012
Create Date: 2026-06-10
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260609_0013'
down_revision: str | None = '20260609_0012'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'outbox',
        sa.Column('idempotency_key', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('target_service', sa.String(length=32), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=16), server_default='PENDING', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(length=2048), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_outbox_id'), 'outbox', ['id'], unique=False)
    op.create_index(op.f('ix_outbox_idempotency_key'), 'outbox', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_outbox_next_retry_at'), 'outbox', ['next_retry_at'], unique=False)
    op.create_index(op.f('ix_outbox_status'), 'outbox', ['status'], unique=False)
    op.create_index(op.f('ix_outbox_target_service'), 'outbox', ['target_service'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_outbox_target_service'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_status'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_next_retry_at'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_idempotency_key'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_id'), table_name='outbox')
    op.drop_table('outbox')
