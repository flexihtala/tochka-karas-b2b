"""create moderators, refresh_tokens, refresh_blacklist tables

Revision ID: 20260520_0001
Revises:
Create Date: 2026-05-20
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260520_0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    op.create_table(
        'moderators',
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_moderators_email'), 'moderators', ['email'], unique=True)
    op.create_index(op.f('ix_moderators_id'), 'moderators', ['id'], unique=False)

    op.create_table(
        'refresh_tokens',
        sa.Column('jti', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['moderators.id']),
        sa.PrimaryKeyConstraint('jti'),
    )
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)

    op.create_table(
        'refresh_blacklist',
        sa.Column('jti', sa.Uuid(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('jti'),
    )


def downgrade() -> None:
    op.drop_table('refresh_blacklist')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index(op.f('ix_moderators_id'), table_name='moderators')
    op.drop_index(op.f('ix_moderators_email'), table_name='moderators')
    op.drop_table('moderators')
