import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.products.enums import ProductStatus
from db import Base, IDMixin, TimestampMixin


class Product(IDMixin, TimestampMixin, Base):
    __tablename__ = 'products'

    seller_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProductStatus] = mapped_column(String(20), nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    category_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('categories.id'), nullable=False)
    images: Mapped[list['ProductImage']] = relationship(
        back_populates='product',
        cascade='all, delete-orphan',
        lazy='selectin',
    )
    characteristics: Mapped[list['ProductCharacteristic']] = relationship(
        back_populates='product',
        cascade='all, delete-orphan',
        lazy='selectin',
    )


class ProductImage(IDMixin, Base):
    __tablename__ = 'product_images'

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('products.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    ordering: Mapped[int] = mapped_column(Integer, nullable=False)
    product: Mapped[Product] = relationship(back_populates='images')


class ProductCharacteristic(IDMixin, Base):
    __tablename__ = 'product_characteristics'

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('products.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    product: Mapped[Product] = relationship(back_populates='characteristics')
