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
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    article: Mapped[str] = mapped_column(String(255), nullable=False)
    cost_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    images: Mapped[list['SKUImage']] = relationship(
        back_populates='sku',
        cascade='all, delete-orphan',
        lazy='selectin',
    )
    characteristics: Mapped[list['SKUCharacteristic']] = relationship(
        back_populates='sku',
        cascade='all, delete-orphan',
        lazy='selectin',
    )


class SKUImage(IDMixin, Base):
    __tablename__ = 'sku_images'

    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('skus.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    ordering: Mapped[int] = mapped_column(Integer, nullable=False)
    sku: Mapped[SKU] = relationship(back_populates='images')


class SKUCharacteristic(IDMixin, Base):
    __tablename__ = 'sku_characteristics'

    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('skus.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[SKU] = relationship(back_populates='characteristics')
