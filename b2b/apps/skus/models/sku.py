import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base, IDMixin, TimestampMixin


class SKU(IDMixin, TimestampMixin, Base):
    __tablename__ = 'skus'

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('products.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_price: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    article: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')

    images: Mapped[list['SKUImage']] = relationship(  # noqa: F821
        'SKUImage',
        cascade='all, delete-orphan',
        lazy='selectin',
        order_by='SKUImage.ordering',
    )
    characteristics: Mapped[list['SKUCharacteristicValue']] = relationship(  # noqa: F821
        'SKUCharacteristicValue',
        cascade='all, delete-orphan',
        lazy='selectin',
    )

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        product_id: uuid.UUID,
        name: str,
        price: int,
        cost_price: int,
        discount: int = 0,
        article: str | None = None,
        active_quantity: int = 0,
        reserved_quantity: int = 0,
    ):
        if id is not None:
            self.id = id
        self.product_id = product_id
        self.name = name
        self.price = price
        self.cost_price = cost_price
        self.discount = discount
        self.article = article
        self.active_quantity = active_quantity
        self.reserved_quantity = reserved_quantity
