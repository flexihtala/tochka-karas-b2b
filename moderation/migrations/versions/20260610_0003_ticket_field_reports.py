"""add field_reports JSONB column to tickets

US-MOD-04 (canon moderation-flows.md#soft-block): замечания модератора по полям товара
персистятся на тикете JSON-массивом. NOT NULL + server_default '[]' — отсутствие
замечаний выражается пустым списком, не NULL (очистка тоже значением []).

Revision ID: 20260610_0003
Revises: 20260520_0002
Create Date: 2026-06-10
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260610_0003'
down_revision: str | None = '20260520_0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'tickets',
        sa.Column(
            'field_reports',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default='[]',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('tickets', 'field_reports')
