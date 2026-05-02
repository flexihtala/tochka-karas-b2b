"""create sku tables

Revision ID: 20260502_0005
Revises: 20260502_0004
Create Date: 2026-05-02
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260502_0005'
down_revision: str | None = '20260502_0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'skus',
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('stock_quantity', sa.Integer(), nullable=False),
        sa.Column('article', sa.String(length=255), nullable=False),
        sa.Column('cost_price', sa.Integer(), nullable=True),
        sa.Column('discount', sa.Integer(), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_skus_id'), 'skus', ['id'], unique=False)
    op.create_index(op.f('ix_skus_product_id'), 'skus', ['product_id'], unique=False)

    op.create_table(
        'sku_images',
        sa.Column('sku_id', sa.Uuid(), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('ordering', sa.Integer(), nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sku_images_id'), 'sku_images', ['id'], unique=False)
    op.create_index(op.f('ix_sku_images_sku_id'), 'sku_images', ['sku_id'], unique=False)

    op.create_table(
        'sku_characteristics',
        sa.Column('sku_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sku_characteristics_id'), 'sku_characteristics', ['id'], unique=False)
    op.create_index(op.f('ix_sku_characteristics_sku_id'), 'sku_characteristics', ['sku_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sku_characteristics_sku_id'), table_name='sku_characteristics')
    op.drop_index(op.f('ix_sku_characteristics_id'), table_name='sku_characteristics')
    op.drop_table('sku_characteristics')
    op.drop_index(op.f('ix_sku_images_sku_id'), table_name='sku_images')
    op.drop_index(op.f('ix_sku_images_id'), table_name='sku_images')
    op.drop_table('sku_images')
    op.drop_index(op.f('ix_skus_product_id'), table_name='skus')
    op.drop_index(op.f('ix_skus_id'), table_name='skus')
    op.drop_table('skus')
