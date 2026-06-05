import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from apps.orders.enums import OrderStatus
from shared.db import Base, IDMixin, TimestampMixin


class Order(IDMixin, TimestampMixin, Base):
    """Заказ покупателя.

    Идемпотентность checkout: UNIQUE-индекс на `idempotency_key` — повторный POST
    с тем же ключом возвращает существующий заказ (см. ADR в этом PR).
    """

    __tablename__ = 'orders'

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=OrderStatus.CREATED.value, index=True)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
    )
    delivery_address: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    address_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    payment_method_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        user_id: uuid.UUID,
        status: str,
        total_amount: int,
        idempotency_key: uuid.UUID,
        delivery_address: str | None = None,
        address_id: uuid.UUID | None = None,
        payment_method_id: uuid.UUID | None = None,
        comment: str | None = None,
    ):
        if id is not None:
            self.id = id
        self.user_id = user_id
        self.status = status
        self.total_amount = total_amount
        self.idempotency_key = idempotency_key
        self.delivery_address = delivery_address
        self.address_id = address_id
        self.payment_method_id = payment_method_id
        self.comment = comment
