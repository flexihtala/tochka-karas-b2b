"""move product details to tables

Revision ID: 20260502_0004
Revises: 20260502_0003
Create Date: 2026-05-02
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260502_0004'
down_revision: str | None = '20260502_0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'product_images',
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('ordering', sa.Integer(), nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_product_images_id'), 'product_images', ['id'], unique=False)
    op.create_index(op.f('ix_product_images_product_id'), 'product_images', ['product_id'], unique=False)

    op.create_table(
        'product_characteristics',
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_product_characteristics_id'), 'product_characteristics', ['id'], unique=False)
    op.create_index(
        op.f('ix_product_characteristics_product_id'),
        'product_characteristics',
        ['product_id'],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO product_images (product_id, url, ordering)
        SELECT products.id, image ->> 'url', (image ->> 'ordering')::integer
        FROM products
        CROSS JOIN LATERAL jsonb_array_elements(products.images) AS image
        """
    )
    op.execute(
        """
        INSERT INTO product_characteristics (product_id, name, value)
        SELECT products.id, characteristic ->> 'name', characteristic ->> 'value'
        FROM products
        CROSS JOIN LATERAL jsonb_array_elements(products.characteristics) AS characteristic
        """
    )

    op.drop_column('products', 'characteristics')
    op.drop_column('products', 'images')


def downgrade() -> None:
    op.add_column('products', sa.Column('images', postgresql.JSONB(), server_default='[]', nullable=False))
    op.add_column('products', sa.Column('characteristics', postgresql.JSONB(), server_default='[]', nullable=False))

    op.execute(
        """
        UPDATE products
        SET images = COALESCE(details.images, '[]'::jsonb)
        FROM (
            SELECT
                product_id,
                jsonb_agg(jsonb_build_object('url', url, 'ordering', ordering) ORDER BY ordering) AS images
            FROM product_images
            GROUP BY product_id
        ) AS details
        WHERE details.product_id = products.id
        """
    )
    op.execute(
        """
        UPDATE products
        SET characteristics = COALESCE(details.characteristics, '[]'::jsonb)
        FROM (
            SELECT
                product_id,
                jsonb_agg(jsonb_build_object('name', name, 'value', value)) AS characteristics
            FROM product_characteristics
            GROUP BY product_id
        ) AS details
        WHERE details.product_id = products.id
        """
    )

    op.drop_index(op.f('ix_product_characteristics_product_id'), table_name='product_characteristics')
    op.drop_index(op.f('ix_product_characteristics_id'), table_name='product_characteristics')
    op.drop_table('product_characteristics')
    op.drop_index(op.f('ix_product_images_product_id'), table_name='product_images')
    op.drop_index(op.f('ix_product_images_id'), table_name='product_images')
    op.drop_table('product_images')
