"""create product tables

Revision ID: 20260502_0002
Revises: 20260502_0001
Create Date: 2026-05-02
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260502_0002'
down_revision: str | None = '20260502_0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_CATEGORY_ID = 'f47ac10b-58cc-4372-a567-0e02b2c3d479'


def upgrade() -> None:
    op.create_table(
        'categories',
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_categories_id'), 'categories', ['id'], unique=False)

    op.create_table(
        'products',
        sa.Column('seller_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('blocked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('category_id', sa.Uuid(), nullable=False),
        sa.Column('images', postgresql.JSONB(), nullable=False),
        sa.Column('characteristics', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_products_id'), 'products', ['id'], unique=False)
    op.create_index(op.f('ix_products_seller_id'), 'products', ['seller_id'], unique=False)

    op.execute(
        sa.text(
            'INSERT INTO categories (id, name) VALUES (:id, :name) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name'
        ).bindparams(id=DEFAULT_CATEGORY_ID, name='iOS')
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_products_seller_id'), table_name='products')
    op.drop_index(op.f('ix_products_id'), table_name='products')
    op.drop_table('products')
    op.drop_index(op.f('ix_categories_id'), table_name='categories')
    op.drop_table('categories')
