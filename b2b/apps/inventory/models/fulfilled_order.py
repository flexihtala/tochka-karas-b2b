"""Модель fulfilled_orders — журнал списанных при доставке резервов (US-B2B-10).

Используется для **идемпотентности по `order_id`** в POST /api/v1/inventory/fulfill:

- UNIQUE(order_id, sku_id) — одна и та же пара никогда не списывается дважды.
- Перед каждым SKU-вычитанием use-case проверяет, нет ли уже строки для этой
  пары; если есть — этот item пропускается (а если по всем items уже есть
  записи — повтор полностью идемпотентен и SKU.reserved_quantity не двигается).

См. ADR-0002: выбран отдельный журнал вместо поля `last_fulfilled_order` на
SKU или эвристики «достаточно reserved_quantity», чтобы исключить риск двойного
списания при ретраях/несинхронных order_id'ах.
"""

import uuid

from sqlalchemy import Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, IDMixin, TimestampMixin


class FulfilledOrder(IDMixin, TimestampMixin, Base):
    __tablename__ = 'fulfilled_orders'
    __table_args__ = (UniqueConstraint('order_id', 'sku_id', name='uq_fulfilled_orders_order_sku'),)

    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    def __init__(
        self,
        *,
        order_id: uuid.UUID,
        sku_id: uuid.UUID,
        quantity: int,
        id: uuid.UUID | None = None,
    ):
        if id is not None:
            self.id = id
        self.order_id = order_id
        self.sku_id = sku_id
        self.quantity = quantity
