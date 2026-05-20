"""SkuUnavailability — кэш статуса недоступности SKU из B2B-событий.

См. ADR (US-ORD-04): cart_items НЕ модифицируется при PRODUCT_BLOCKED / DELETED /
SKU_OUT_OF_STOCK; вместо этого мы сохраняем sku_id → reason здесь. GET /cart
обогащается из B2B и считает истиной B2B-ответ, но эта таблица отражает
последнее известное состояние недоступности, локальное для B2C.

PK = sku_id (один SKU имеет один актуальный reason). При повторном событии
upsert обновит reason / event_idempotency_key.
"""

import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, TimestampMixin


class SkuUnavailability(TimestampMixin, Base):
    """Кэш недоступных SKU из событий B2B (BLOCKED, DELETED, OUT_OF_STOCK)."""

    __tablename__ = 'sku_unavailability'

    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    event_idempotency_key: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    def __init__(
        self,
        *,
        sku_id: uuid.UUID,
        reason: str,
        product_id: uuid.UUID,
        event_idempotency_key: uuid.UUID,
    ):
        self.sku_id = sku_id
        self.reason = reason
        self.product_id = product_id
        self.event_idempotency_key = event_idempotency_key
