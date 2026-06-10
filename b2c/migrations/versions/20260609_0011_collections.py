"""create b2c collections + collection_items (US-CART-05)

Revision ID: 20260609_0011
Revises: 20260609_0010
Create Date: 2026-06-10
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260609_0011'
down_revision: str | None = '20260609_0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'collections',
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('position', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_collections_id'), 'collections', ['id'], unique=False)
    op.create_index(op.f('ix_collections_slug'), 'collections', ['slug'], unique=True)
    op.create_index(
        'ix_collections_active_position',
        'collections',
        ['position'],
        postgresql_where=sa.text('is_active = true'),
    )

    op.create_table(
        'collection_items',
        sa.Column('collection_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('ordering', sa.Integer(), server_default='0', nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('collection_id', 'product_id', name='uq_collection_items_collection_product'),
    )
    op.create_index(op.f('ix_collection_items_id'), 'collection_items', ['id'], unique=False)
    op.create_index(op.f('ix_collection_items_collection_id'), 'collection_items', ['collection_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_collection_items_collection_id'), table_name='collection_items')
    op.drop_index(op.f('ix_collection_items_id'), table_name='collection_items')
    op.drop_table('collection_items')

    op.drop_index('ix_collections_active_position', table_name='collections')
    op.drop_index(op.f('ix_collections_slug'), table_name='collections')
    op.drop_index(op.f('ix_collections_id'), table_name='collections')
    op.drop_table('collections')
