import uuid

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import String

from shared.db import Base, IDMixin, TimestampMixin


class Subscription(IDMixin, TimestampMixin, Base):
    """Подписка покупателя на уведомления о товаре.

    UNIQUE(user_id, product_id) — на уровне БД гарантирует одну подписку
    на пару пользователь/товар. Повторная попытка приводит к 409.

    notify_on хранится как ARRAY[str] (PG ARRAY) — события, на которые
    подписан пользователь (PRICE_DROP, BACK_IN_STOCK). Решение по storage
    — см. ADR в b2c/README.md.
    """

    __tablename__ = 'product_subscriptions'
    __table_args__ = (UniqueConstraint('user_id', 'product_id', name='uq_product_subscriptions_user_product'),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    notify_on: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        notify_on: list[str],
    ):
        if id is not None:
            self.id = id
        self.user_id = user_id
        self.product_id = product_id
        self.notify_on = notify_on
