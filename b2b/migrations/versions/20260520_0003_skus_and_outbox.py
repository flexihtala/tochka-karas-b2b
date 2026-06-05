"""create skus, sku_images, sku_characteristic_values, outbox tables

Revision ID: 20260520_0003
Revises: 20260520_0002
Create Date: 2026-05-20
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260520_0003'
down_revision: str | None = '20260520_0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'skus',
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('cost_price', sa.Integer(), nullable=False),
        sa.Column('discount', sa.Integer(), server_default='0', nullable=False),
        sa.Column('article', sa.String(length=255), nullable=True),
        sa.Column('active_quantity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('reserved_quantity', sa.Integer(), server_default='0', nullable=False),
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
        sa.Column('ordering', sa.Integer(), server_default='0', nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sku_images_id'), 'sku_images', ['id'], unique=False)
    op.create_index(op.f('ix_sku_images_sku_id'), 'sku_images', ['sku_id'], unique=False)

    op.create_table(
        'sku_characteristic_values',
        sa.Column('sku_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('value', sa.String(length=1024), nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sku_characteristic_values_id'), 'sku_characteristic_values', ['id'], unique=False)
    op.create_index(op.f('ix_sku_characteristic_values_sku_id'), 'sku_characteristic_values', ['sku_id'], unique=False)

    op.create_table(
        'outbox',
        sa.Column('idempotency_key', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('target_service', sa.String(length=32), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=16), server_default='PENDING', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(length=2048), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_outbox_id'), 'outbox', ['id'], unique=False)
    op.create_index(op.f('ix_outbox_idempotency_key'), 'outbox', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_outbox_next_retry_at'), 'outbox', ['next_retry_at'], unique=False)
    op.create_index(op.f('ix_outbox_status'), 'outbox', ['status'], unique=False)
    op.create_index(op.f('ix_outbox_target_service'), 'outbox', ['target_service'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_outbox_target_service'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_status'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_next_retry_at'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_idempotency_key'), table_name='outbox')
    op.drop_index(op.f('ix_outbox_id'), table_name='outbox')
    op.drop_table('outbox')

    op.drop_index(op.f('ix_sku_characteristic_values_sku_id'), table_name='sku_characteristic_values')
    op.drop_index(op.f('ix_sku_characteristic_values_id'), table_name='sku_characteristic_values')
    op.drop_table('sku_characteristic_values')

    op.drop_index(op.f('ix_sku_images_sku_id'), table_name='sku_images')
    op.drop_index(op.f('ix_sku_images_id'), table_name='sku_images')
    op.drop_table('sku_images')

    op.drop_index(op.f('ix_skus_product_id'), table_name='skus')
    op.drop_index(op.f('ix_skus_id'), table_name='skus')
    op.drop_table('skus')
