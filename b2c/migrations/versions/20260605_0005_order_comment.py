"""add orders.comment (nullable) for checkout comment (US-ORD-01, spec OrderCreateRequest)

Revision ID: 20260605_0005
Revises: 20260605_0004
Create Date: 2026-06-05
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260605_0005'
down_revision: str | None = '20260605_0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('comment', sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'comment')
