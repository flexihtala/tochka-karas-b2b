"""create fulfilled_orders table (inventory fulfill idempotency)

Revision ID: 20260520_0005
Revises: 20260520_0004
Create Date: 2026-05-20

Создаёт таблицу fulfilled_orders — журнал списаний резерва при доставке
(POST /api/v1/inventory/fulfill, US-B2B-10). Идемпотентность по `order_id`:
UNIQUE(order_id, sku_id) защищает от двойного списания при повторных
вызовах и параллельных гонках с одинаковым order_id.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260520_0005'
down_revision: str | None = '20260520_0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'fulfilled_orders',
        sa.Column('order_id', sa.Uuid(), nullable=False),
        sa.Column('sku_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id', 'sku_id', name='uq_fulfilled_orders_order_sku'),
    )
    op.create_index(op.f('ix_fulfilled_orders_id'), 'fulfilled_orders', ['id'], unique=False)
    op.create_index(op.f('ix_fulfilled_orders_order_id'), 'fulfilled_orders', ['order_id'], unique=False)
    op.create_index(op.f('ix_fulfilled_orders_sku_id'), 'fulfilled_orders', ['sku_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fulfilled_orders_sku_id'), table_name='fulfilled_orders')
    op.drop_index(op.f('ix_fulfilled_orders_order_id'), table_name='fulfilled_orders')
    op.drop_index(op.f('ix_fulfilled_orders_id'), table_name='fulfilled_orders')
    op.drop_table('fulfilled_orders')
