"""create invoices, invoice_items tables

Revision ID: 20260520_0004
Revises: 20260520_0003
Create Date: 2026-05-20
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260520_0004'
down_revision: str | None = '20260520_0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'invoices',
        sa.Column('seller_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='CREATED', nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['seller_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_invoices_id'), 'invoices', ['id'], unique=False)
    op.create_index(op.f('ix_invoices_seller_id'), 'invoices', ['seller_id'], unique=False)

    op.create_table(
        'invoice_items',
        sa.Column('invoice_id', sa.Uuid(), nullable=False),
        sa.Column('sku_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('accepted_quantity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sku_id'], ['skus.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_invoice_items_id'), 'invoice_items', ['id'], unique=False)
    op.create_index(op.f('ix_invoice_items_invoice_id'), 'invoice_items', ['invoice_id'], unique=False)
    op.create_index(op.f('ix_invoice_items_sku_id'), 'invoice_items', ['sku_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_invoice_items_sku_id'), table_name='invoice_items')
    op.drop_index(op.f('ix_invoice_items_invoice_id'), table_name='invoice_items')
    op.drop_index(op.f('ix_invoice_items_id'), table_name='invoice_items')
    op.drop_table('invoice_items')

    op.drop_index(op.f('ix_invoices_seller_id'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_id'), table_name='invoices')
    op.drop_table('invoices')
