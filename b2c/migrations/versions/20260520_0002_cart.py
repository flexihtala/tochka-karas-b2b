"""create cart tables: carts, cart_items

Revision ID: 20260520_0002
Revises: 20260520_0001
Create Date: 2026-05-20
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260520_0002'
down_revision: str | None = '20260520_0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'carts',
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('session_id', sa.String(length=64), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('(user_id IS NOT NULL) OR (session_id IS NOT NULL)', name='cart_identity_present'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_carts_id'), 'carts', ['id'], unique=False)
    op.create_index(op.f('ix_carts_user_id'), 'carts', ['user_id'], unique=True)
    op.create_index(op.f('ix_carts_session_id'), 'carts', ['session_id'], unique=True)

    op.create_table(
        'cart_items',
        sa.Column('cart_id', sa.Uuid(), nullable=False),
        sa.Column('sku_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('quantity >= 1', name='cart_item_quantity_positive'),
        sa.ForeignKeyConstraint(['cart_id'], ['carts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cart_id', 'sku_id', name='uq_cart_items_cart_sku'),
    )
    op.create_index(op.f('ix_cart_items_id'), 'cart_items', ['id'], unique=False)
    op.create_index(op.f('ix_cart_items_cart_id'), 'cart_items', ['cart_id'], unique=False)
    op.create_index(op.f('ix_cart_items_sku_id'), 'cart_items', ['sku_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_cart_items_sku_id'), table_name='cart_items')
    op.drop_index(op.f('ix_cart_items_cart_id'), table_name='cart_items')
    op.drop_index(op.f('ix_cart_items_id'), table_name='cart_items')
    op.drop_table('cart_items')

    op.drop_index(op.f('ix_carts_session_id'), table_name='carts')
    op.drop_index(op.f('ix_carts_user_id'), table_name='carts')
    op.drop_index(op.f('ix_carts_id'), table_name='carts')
    op.drop_table('carts')
