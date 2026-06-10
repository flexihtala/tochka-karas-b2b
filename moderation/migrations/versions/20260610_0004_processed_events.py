"""create processed_events inbox table

US-MOD-01: идемпотентность входящего канала POST /api/v1/b2b/events.
UNIQUE(sender_service, idempotency_key) — арбитр гонки: ключ вставляется ДО
мутаций тикетов, повторное/конкурентное событие ловит IntegrityError → 409
DUPLICATE_EVENT. created_at играет роль received_at; TTL-очистка 24h —
DELETE WHERE created_at < now() - interval '24 hours' (scheduled job, вне scope).

Revision ID: 20260610_0004
Revises: 20260610_0003
Create Date: 2026-06-10
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260610_0004'
down_revision: str | None = '20260610_0003'
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
        sa.UniqueConstraint('sender_service', 'idempotency_key', name='uq_processed_events_sender_key'),
    )
    op.create_index(op.f('ix_processed_events_id'), 'processed_events', ['id'], unique=False)
    op.create_index(op.f('ix_processed_events_sender_service'), 'processed_events', ['sender_service'], unique=False)
    op.create_index(op.f('ix_processed_events_idempotency_key'), 'processed_events', ['idempotency_key'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_processed_events_idempotency_key'), table_name='processed_events')
    op.drop_index(op.f('ix_processed_events_sender_service'), table_name='processed_events')
    op.drop_index(op.f('ix_processed_events_id'), table_name='processed_events')
    op.drop_table('processed_events')
