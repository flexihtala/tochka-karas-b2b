"""move product details to jsonb

Revision ID: 20260502_0003
Revises: 20260502_0002
Create Date: 2026-05-02
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260502_0003'
down_revision: str | None = '20260502_0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table('product_characteristics', if_exists=True)
    op.drop_table('product_images', if_exists=True)
    op.add_column('products', sa.Column('images', postgresql.JSONB(), nullable=True), if_not_exists=True)
    op.add_column(
        'products',
        sa.Column('characteristics', postgresql.JSONB(), server_default='[]', nullable=True),
        if_not_exists=True,
    )
    op.execute("UPDATE products SET images = '[]'::jsonb WHERE images IS NULL")
    op.execute("UPDATE products SET characteristics = '[]'::jsonb WHERE characteristics IS NULL")
    op.alter_column('products', 'images', nullable=False)
    op.alter_column('products', 'characteristics', nullable=False)


def downgrade() -> None:
    op.drop_column('products', 'characteristics', if_exists=True)
    op.drop_column('products', 'images', if_exists=True)
