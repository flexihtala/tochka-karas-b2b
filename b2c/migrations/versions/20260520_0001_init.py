"""create b2c initial tables: users, refresh_tokens, refresh_blacklist, addresses, payment_methods

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
        'users',
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    op.create_table(
        'refresh_tokens',
        sa.Column('jti', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
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

    op.create_table(
        'addresses',
        sa.Column('buyer_id', sa.Uuid(), nullable=False),
        sa.Column('country', sa.String(length=100), nullable=False),
        sa.Column('city', sa.String(length=200), nullable=False),
        sa.Column('street', sa.String(length=200), nullable=False),
        sa.Column('postal_code', sa.String(length=20), nullable=False),
        sa.Column('comment', sa.String(length=500), nullable=True),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['buyer_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_addresses_buyer_id'), 'addresses', ['buyer_id'], unique=False)
    op.create_index(op.f('ix_addresses_id'), 'addresses', ['id'], unique=False)

    op.create_table(
        'payment_methods',
        sa.Column('buyer_id', sa.Uuid(), nullable=False),
        sa.Column('brand', sa.String(length=32), nullable=False),
        sa.Column('last4', sa.String(length=4), nullable=False),
        sa.Column('exp_year', sa.Integer(), nullable=False),
        sa.Column('exp_month', sa.Integer(), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['buyer_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_payment_methods_buyer_id'), 'payment_methods', ['buyer_id'], unique=False)
    op.create_index(op.f('ix_payment_methods_id'), 'payment_methods', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payment_methods_id'), table_name='payment_methods')
    op.drop_index(op.f('ix_payment_methods_buyer_id'), table_name='payment_methods')
    op.drop_table('payment_methods')

    op.drop_index(op.f('ix_addresses_id'), table_name='addresses')
    op.drop_index(op.f('ix_addresses_buyer_id'), table_name='addresses')
    op.drop_table('addresses')

    op.drop_table('refresh_blacklist')

    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')

    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
