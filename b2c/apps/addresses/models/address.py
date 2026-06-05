import uuid

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class Address(IDMixin, TimestampMixin, Base):
    """Адрес доставки покупателя. buyer_id ссылается на users.id."""

    __tablename__ = 'addresses'

    buyer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True, nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(200), nullable=False)
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        buyer_id: uuid.UUID,
        country: str,
        city: str,
        street: str,
        postal_code: str,
        comment: str | None = None,
        is_default: bool = False,
    ):
        if id is not None:
            self.id = id
        self.buyer_id = buyer_id
        self.country = country
        self.city = city
        self.street = street
        self.postal_code = postal_code
        self.comment = comment
        self.is_default = is_default
