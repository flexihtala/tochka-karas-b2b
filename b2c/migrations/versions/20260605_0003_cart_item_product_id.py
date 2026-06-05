"""add cart_items.product_id (nullable) for batch-by-product B2B enrichment

Revision ID: 20260605_0003
Revises: 20260520_0002
Create Date: 2026-06-05
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260605_0003'
down_revision: str | None = '20260520_0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('cart_items', sa.Column('product_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_cart_items_product_id'), 'cart_items', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_cart_items_product_id'), table_name='cart_items')
    op.drop_column('cart_items', 'product_id')
