"""create orders and order_items tables (US-ORD-01)

Revision ID: 20260605_0004
Revises: 20260605_0003
Create Date: 2026-06-05
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260605_0004'
down_revision: str | None = '20260605_0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'orders',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('total_amount', sa.Integer(), nullable=False),
        sa.Column('idempotency_key', sa.Uuid(), nullable=False),
        sa.Column('delivery_address', sa.String(length=1024), nullable=True),
        sa.Column('address_id', sa.Uuid(), nullable=True),
        sa.Column('payment_method_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_orders_id'), 'orders', ['id'], unique=False)
    op.create_index(op.f('ix_orders_user_id'), 'orders', ['user_id'], unique=False)
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)
    op.create_index(op.f('ix_orders_idempotency_key'), 'orders', ['idempotency_key'], unique=True)

    op.create_table(
        'order_items',
        sa.Column('order_id', sa.Uuid(), nullable=False),
        sa.Column('sku_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('product_title', sa.String(length=500), nullable=False),
        sa.Column('sku_name', sa.String(length=500), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Integer(), nullable=False),
        sa.Column('line_total', sa.Integer(), nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_order_items_id'), 'order_items', ['id'], unique=False)
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)
    op.create_index(op.f('ix_order_items_sku_id'), 'order_items', ['sku_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_order_items_sku_id'), table_name='order_items')
    op.drop_index(op.f('ix_order_items_order_id'), table_name='order_items')
    op.drop_index(op.f('ix_order_items_id'), table_name='order_items')
    op.drop_table('order_items')

    op.drop_index(op.f('ix_orders_idempotency_key'), table_name='orders')
    op.drop_index(op.f('ix_orders_status'), table_name='orders')
    op.drop_index(op.f('ix_orders_user_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_id'), table_name='orders')
    op.drop_table('orders')
