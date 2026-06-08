"""add products.field_reports and products.blocking_reason_title

US-B2B-05 (карточка товара продавца) приводит ответ к openapi ProductDetailResponse:
- field_reports — массив FieldReport ({field_name, sku_id?, comment}), хранится как JSONB;
- blocking_reason_title — title причины блокировки (для объекта blocking_reason).

Обе колонки заполняются flow модерации (US-B2B-09, обработчик MODERATED/BLOCKED-событий);
до этого момента остаются пустыми (field_reports=[] / blocking_reason_title=NULL).

Revision ID: 20260602_0005
Revises: 20260521_0004
Create Date: 2026-06-02
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '20260602_0005'
down_revision: str | None = '20260521_0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('products', sa.Column('blocking_reason_title', sa.Text(), nullable=True))
    op.add_column(
        'products',
        sa.Column(
            'field_reports',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default='[]',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('products', 'field_reports')
    op.drop_column('products', 'blocking_reason_title')
