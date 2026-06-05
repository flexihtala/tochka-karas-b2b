import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class PaymentMethod(IDMixin, TimestampMixin, Base):
    """Платёжный метод покупателя — ХРАНИМ ТОЛЬКО МЕТАДАННЫЕ.

    НЕТ полного PAN, CVC, expiry в чистом виде вне brand/last4/exp_year/exp_month.
    """

    __tablename__ = 'payment_methods'

    buyer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True, nullable=False)
    brand: Mapped[str] = mapped_column(String(32), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    exp_year: Mapped[int] = mapped_column(Integer, nullable=False)
    exp_month: Mapped[int] = mapped_column(Integer, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        buyer_id: uuid.UUID,
        brand: str,
        last4: str,
        exp_year: int,
        exp_month: int,
        is_default: bool = False,
    ):
        if id is not None:
            self.id = id
        self.buyer_id = buyer_id
        self.brand = brand
        self.last4 = last4
        self.exp_year = exp_year
        self.exp_month = exp_month
        self.is_default = is_default
