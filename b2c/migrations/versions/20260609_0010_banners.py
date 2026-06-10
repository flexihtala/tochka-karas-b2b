"""create b2c banners + banner_clicks (US-CART-04)

Revision ID: 20260609_0010
Revises: 20260609_0009
Create Date: 2026-06-10
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260609_0010'
down_revision: str | None = '20260609_0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'banners',
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('image_url', sa.String(length=1024), nullable=False),
        sa.Column('link_url', sa.String(length=1024), nullable=False),
        sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('schedule_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('schedule_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_banners_id'), 'banners', ['id'], unique=False)
    # Партиал-индекс для горячего пути GET /home/banners:
    op.create_index(
        'ix_banners_active_priority',
        'banners',
        [sa.text('priority DESC')],
        postgresql_where=sa.text('is_active = true'),
    )

    op.create_table(
        'banner_clicks',
        sa.Column('banner_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['banner_id'], ['banners.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_banner_clicks_id'), 'banner_clicks', ['id'], unique=False)
    op.create_index(op.f('ix_banner_clicks_banner_id'), 'banner_clicks', ['banner_id'], unique=False)
    op.create_index(op.f('ix_banner_clicks_user_id'), 'banner_clicks', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_banner_clicks_user_id'), table_name='banner_clicks')
    op.drop_index(op.f('ix_banner_clicks_banner_id'), table_name='banner_clicks')
    op.drop_index(op.f('ix_banner_clicks_id'), table_name='banner_clicks')
    op.drop_table('banner_clicks')

    op.drop_index('ix_banners_active_priority', table_name='banners')
    op.drop_index(op.f('ix_banners_id'), table_name='banners')
    op.drop_table('banners')
