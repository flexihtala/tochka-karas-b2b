"""add orders.cancel_reason (nullable) for order cancellation (US-ORD-03, spec OrderResponse.cancel_reason)

Revision ID: 20260605_0006
Revises: 20260605_0005
Create Date: 2026-06-05
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260605_0006'
down_revision: str | None = '20260605_0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('cancel_reason', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'cancel_reason')
