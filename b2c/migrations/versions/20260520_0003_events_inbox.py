"""create events / inbox tables: processed_events, sku_unavailability

Revision ID: 20260520_0003
Revises: 20260520_0002
Create Date: 2026-05-20
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260520_0003'
down_revision: str | None = '20260520_0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'processed_events',
        sa.Column('sender_service', sa.String(length=32), nullable=False),
        sa.Column('idempotency_key', sa.Uuid(), nullable=False),
        sa.Column('response_cached', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sender_service', 'idempotency_key', name='uq_processed_events_sender_key'),
    )
    op.create_index(op.f('ix_processed_events_id'), 'processed_events', ['id'], unique=False)
    op.create_index(op.f('ix_processed_events_sender_service'), 'processed_events', ['sender_service'], unique=False)
    op.create_index(op.f('ix_processed_events_idempotency_key'), 'processed_events', ['idempotency_key'], unique=False)

    op.create_table(
        'sku_unavailability',
        sa.Column('sku_id', sa.Uuid(), nullable=False),
        sa.Column('reason', sa.String(length=32), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('event_idempotency_key', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('sku_id'),
    )
    op.create_index(op.f('ix_sku_unavailability_product_id'), 'sku_unavailability', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sku_unavailability_product_id'), table_name='sku_unavailability')
    op.drop_table('sku_unavailability')

    op.drop_index(op.f('ix_processed_events_idempotency_key'), table_name='processed_events')
    op.drop_index(op.f('ix_processed_events_sender_service'), table_name='processed_events')
    op.drop_index(op.f('ix_processed_events_id'), table_name='processed_events')
    op.drop_table('processed_events')
