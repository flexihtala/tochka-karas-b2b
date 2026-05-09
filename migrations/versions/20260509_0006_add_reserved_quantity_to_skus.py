"""add reserved_quantity to skus

Revision ID: 20260509_0006
Revises: 20260502_0005
Create Date: 2026-05-09
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260509_0006'
down_revision: str | None = '20260502_0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'skus',
        sa.Column('reserved_quantity', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('skus', 'reserved_quantity')
