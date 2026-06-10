"""create processed_events table (inbox idempotency)

Revision ID: 20260605_0006
Revises: 20260602_0005
Create Date: 2026-05-20

Re-chained after main's head (0005_product_field_reports) when US-B2B-08 merged,
to keep a single linear alembic history.

Создаёт таблицу processed_events: at-most-once семантика для входящих
service-to-service запросов с idempotency_key (включая POST /inventory/reserve,
/inventory/unreserve, /moderation/events). UNIQUE(sender_service, idempotency_key)
гарантирует, что повторный запрос будет обнаружен и обработан как дубликат.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260605_0006'
down_revision: str | None = '20260602_0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'processed_events',
        sa.Column('sender_service', sa.String(length=32), nullable=False),
        sa.Column('idempotency_key', sa.Uuid(), nullable=False),
        sa.Column('response_cached', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sender_service', 'idempotency_key', name='uq_inbox_sender_key'),
    )
    op.create_index(op.f('ix_processed_events_id'), 'processed_events', ['id'], unique=False)
    op.create_index(
        op.f('ix_processed_events_sender_service'),
        'processed_events',
        ['sender_service'],
        unique=False,
    )
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
