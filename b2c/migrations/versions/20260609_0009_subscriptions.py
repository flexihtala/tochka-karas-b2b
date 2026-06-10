"""create b2c product_subscriptions table

Revision ID: 20260609_0009
Revises: 20260609_0008
Create Date: 2026-06-09
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260609_0009'
down_revision: str | None = '20260609_0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'product_subscriptions',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('notify_on', sa.dialects.postgresql.ARRAY(sa.String(length=32)), nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'product_id', name='uq_product_subscriptions_user_product'),
    )
    op.create_index(op.f('ix_product_subscriptions_id'), 'product_subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_product_subscriptions_user_id'), 'product_subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_product_subscriptions_product_id'), 'product_subscriptions', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_product_subscriptions_product_id'), table_name='product_subscriptions')
    op.drop_index(op.f('ix_product_subscriptions_user_id'), table_name='product_subscriptions')
    op.drop_index(op.f('ix_product_subscriptions_id'), table_name='product_subscriptions')
    op.drop_table('product_subscriptions')
