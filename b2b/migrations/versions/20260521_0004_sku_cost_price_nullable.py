"""make skus.cost_price nullable

Per neomarket-protocols/b2b/openapi.yaml SKUCreate: cost_price is nullable
and NOT in required. The original migration made the column NOT NULL,
which causes the API to 422-reject conformant clients that omit the field.

Revision ID: 20260521_0004
Revises: 20260520_0003
Create Date: 2026-05-21
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '20260521_0004'
down_revision: str | None = '20260520_0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        'skus',
        'cost_price',
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'skus',
        'cost_price',
        existing_type=sa.Integer(),
        nullable=False,
    )
