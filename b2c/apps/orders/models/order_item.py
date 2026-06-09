import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class OrderItem(IDMixin, TimestampMixin, Base):
    """Позиция заказа.

    `unit_price`, `product_title`, `sku_name`, `product_id` — снапшот на момент
    покупки (см. канон: покупатель видит то, что покупал, даже если продавец
    позже изменил цену или название).
    """

    __tablename__ = 'order_items'

    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('orders.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    product_title: Mapped[str] = mapped_column(String(500), nullable=False)
    sku_name: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[int] = mapped_column(Integer, nullable=False)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        order_id: uuid.UUID,
        sku_id: uuid.UUID,
        product_id: uuid.UUID,
        product_title: str,
        sku_name: str,
        quantity: int,
        unit_price: int,
        line_total: int,
    ):
        if id is not None:
            self.id = id
        self.order_id = order_id
        self.sku_id = sku_id
        self.product_id = product_id
        self.product_title = product_title
        self.sku_name = sku_name
        self.quantity = quantity
        self.unit_price = unit_price
        self.line_total = line_total
